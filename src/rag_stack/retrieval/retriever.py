import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from qdrant_client import QdrantClient, models

from rag_stack import observability
from rag_stack.config import Settings
from rag_stack.db.edges import EdgeGraph
from rag_stack.ingestion.models import Chunk
from rag_stack.ingestion.registry import SOURCES
from rag_stack.llm.embeddings import Embedder, Reranker, SparseEmbedder
from rag_stack.retrieval.fusion import rrf
from rag_stack.retrieval.ids import detect_ids
from rag_stack.retrieval.language import detect_language

# Words asking how to defend (defend, defence, harden; schützen, absichern, ...).
DEFENSE = (
    r"mitigat|countermeasure|defen|prevent|protect|safeguard|harden|"
    r"gegenma|abwehr|schutz|schütz|minder|verteidig|absicher|härt"
)
# Questions about related items get the 1-hop neighbors of the units they are about.
RELATED = re.compile(
    DEFENSE + r"|map|relat|correspond|link|connect|technique|tactic|weakness|cwe|"
    r"zuordn|verwandt|bezug|zusammenh|entsprech|verknüpf",
    re.I,
)
MITIGATIONS = re.compile(DEFENSE, re.I)
MAX_PER_ID = 6  # parts of a named article or annex
MAX_PER_UNIT = 3  # sections of one named unit (an OWASP entry has eight or more)
MAX_NEIGHBORS = 12


@dataclass(frozen=True)
class Retrieved:
    chunk: Chunk
    score: float
    # How it was found: "id" (named in the question), "graph" (related to one) or "hybrid".
    via: str


class Retriever(Protocol):
    async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
        """Ranked chunks for a question; `context` is the previous question, for follow-ups."""
        ...

    async def catalog(self) -> list[str]:
        """The names of the indexed sources, e.g. 'MITRE ATLAS', each once."""
        ...


def any_of(key: str, values: list[str]) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchAny(any=values))


class KnowledgeBase:
    """Exact IDs first, then dense + BM25 fused with RRF, a cross-encoder rerank, 1-hop graph
    expansion for questions about related items, and legal text in the question's language."""

    def __init__(
        self,
        client: QdrantClient,
        collection: str,
        embedder: Embedder,
        sparse: SparseEmbedder,
        reranker: Reranker,
        graph: EdgeGraph,
        *,
        candidates: int = 50,
        limit: int = 10,
        min_score: float = 0.0,
        rerank_chars: int = 1000,
    ) -> None:
        self.client = client
        self.collection = collection
        self.embedder = embedder
        self.sparse = sparse
        self.reranker = reranker
        self.graph = graph
        self.candidates = candidates
        self.limit = limit
        self.min_score = min_score
        self.rerank_chars = rerank_chars

    async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
        # Embedding, reranking and the (sync) Qdrant client all block: keep them off the loop.
        return await asyncio.to_thread(self._retrieve, query, context)

    async def catalog(self) -> list[str]:
        facets = await asyncio.to_thread(self.client.facet, self.collection, "source_id", limit=50)
        return sorted(SOURCES[str(hit.value)].name for hit in facets.hits)

    def _retrieve(self, query: str, context: str) -> list[Retrieved]:
        language = detect_language(query)
        ids = detect_ids(query)
        search = query
        if not ids and (ids := detect_ids(context)):
            # shortcut: a follow-up without IDs ("How do I defend against it?") reuses the
            # previous question's IDs and searches with both questions instead of an LLM query
            # rewrite; add a rewrite step if follow-ups need more than that.
            search = f"{context} {query}"
        with observability.stage("id lookup"):
            exact = self.by_ids(ids)
        seeds = list(dict.fromkeys(c.native_id for c in exact if c.native_id in ids))
        with observability.stage("hybrid search"):
            hybrid = self._hybrid(search)
        if not seeds:
            seeds = [hybrid[0].native_id] if hybrid else []
        with observability.stage("graph expansion"):
            related = self._neighbors(query, seeds) if RELATED.search(query) else []

        pool = unique([*exact, *related, *hybrid])
        with observability.stage("rerank"):
            scores = dict(
                zip(
                    [c.point_id for c in pool],
                    self.reranker.rerank(
                        search, [c.embedding_text()[: self.rerank_chars] for c in pool]
                    )
                    if pool
                    else [],
                    strict=True,
                )
            )

        # A chunk found by search as well as through an edge keeps the edge's relation label.
        annotated = {c.point_id: c for c in related}

        def ranked(chunks: list[Chunk], via: str) -> list[Retrieved]:
            return sorted(
                (Retrieved(annotated.get(c.point_id, c), scores[c.point_id], via) for c in chunks),
                key=lambda r: -r.score,
            )

        named = [c for c in exact if c.native_id in ids or set(c.aliases) & set(ids)]

        def parent_of(chunk: Chunk) -> str:
            return next((i for i in ids if i in chunk.parent_ids), chunk.native_id)

        parts = [c for c in exact if c not in named]
        relevant = [r for r in ranked(hybrid, "hybrid") if r.score >= self.min_score]
        if not exact:
            # No IDs named: the search hits lead, the neighbors of the top one follow. Without
            # a relevant hit there is nothing to relate to, so the answer is an abstention.
            found = [*relevant, *ranked(related, "graph")] if relevant else []
        else:
            # Named units, then units related to them, then parts of named articles and annexes.
            found = [
                *self._cap(ranked(named, "id"), lambda c: c.native_id, MAX_PER_UNIT),
                *ranked(related, "graph"),
                *self._cap(ranked(parts, "id"), parent_of, MAX_PER_ID),
                *relevant,
            ]
        with observability.stage("language"):
            return self._in_language(found, language)[: self.limit]

    def _scroll(self, flt: models.Filter) -> list[Chunk]:
        """Every point matching the filter, page by page."""
        chunks: list[Chunk] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                self.collection, scroll_filter=flt, limit=256, offset=offset
            )
            chunks += [Chunk.model_validate(p.payload) for p in points]
            if offset is None:
                return chunks

    def by_ids(self, ids: list[str]) -> list[Chunk]:
        if not ids:
            return []
        keys = ("native_id", "parent_ids", "aliases")
        return self._scroll(models.Filter(should=[any_of(k, ids) for k in keys]))

    @staticmethod
    def _cap(found: list[Retrieved], group: Callable[[Chunk], str], limit: int) -> list[Retrieved]:
        """Keep the best `limit` sections per group. A section is (native_id, chunk_index), so
        its English and German copies count once; the language swap later keeps one of them."""
        kept, sections = [], {}
        for r in found:
            seen = sections.setdefault(group(r.chunk), set())
            section = (r.chunk.native_id, r.chunk.chunk_index)
            if section in seen or len(seen) < limit:
                seen.add(section)
                kept.append(r)
        return kept

    def _hybrid(self, query: str) -> list[Chunk]:
        sparse = self.sparse.embed_query(query)
        dense, lexical = self.client.query_batch_points(
            self.collection,
            [
                models.QueryRequest(
                    query=self.embedder.embed_query(query),
                    using="dense",
                    limit=self.candidates,
                    with_payload=True,
                ),
                models.QueryRequest(
                    query=models.SparseVector(indices=sparse.indices, values=sparse.values),
                    using="bm25",
                    limit=self.candidates,
                    with_payload=True,
                ),
            ],
        )
        payloads = {p.id: p.payload for p in [*dense.points, *lexical.points]}
        fused = rrf([[p.id for p in dense.points], [p.id for p in lexical.points]])
        return [Chunk.model_validate(payloads[i]) for i in fused[: self.candidates]]

    def _neighbors(self, query: str, seeds: list[str]) -> list[Chunk]:
        """The first chunk of each unit one hop from the seeds, labeled with the relation
        (the edge is not in either unit's text, so the model needs it spelled out)."""
        rels = {"mitigates"} if MITIGATIONS.search(query) else None
        relation: dict[str, str] = {}
        for seed in seeds[:3]:
            for edge in self.graph.edges(seed, rels):
                other = edge.dst_id if edge.src_id == seed else edge.src_id
                if other not in seeds:
                    relation.setdefault(other, f"{edge.src_id} {edge.rel} {edge.dst_id}")
        if not relation:
            return []
        flt = models.Filter(must=[any_of("native_id", list(relation))])
        # Edges may point outside the corpus (ATT&CK, CWE): cap only what exists.
        chunks = [c for c in self._scroll(flt) if c.chunk_index == 0]
        chunks.sort(key=lambda c: list(relation).index(c.native_id))
        return [
            c.model_copy(update={"meta": {**c.meta, "relation": relation[c.native_id]}})
            for c in chunks[:MAX_NEIGHBORS]
        ]

    def _in_language(self, found: list[Retrieved], language: str) -> list[Retrieved]:
        """Swap legal text to its twin in the question's language, then drop duplicates."""
        other = [
            r.chunk.unit_key for r in found if r.chunk.unit_key and r.chunk.language != language
        ]
        twins = {}
        if other:
            flt = models.Filter(
                must=[
                    any_of("unit_key", list(dict.fromkeys(other))),
                    models.FieldCondition(key="language", match=models.MatchValue(value=language)),
                ]
            )
            twins = {(c.unit_key, c.chunk_index): c for c in self._scroll(flt)}
        seen, out = set(), []
        for r in found:
            key = r.chunk.unit_key
            twin = twins.get((key, r.chunk.chunk_index)) or twins.get((key, 0))
            r = Retrieved(twin, r.score, r.via) if twin else r
            if r.chunk.point_id not in seen:
                seen.add(r.chunk.point_id)
                out.append(r)
        return out


def unique(chunks: list[Chunk]) -> list[Chunk]:
    return list({c.point_id: c for c in chunks}.values())


def knowledge_base(
    settings: Settings,
    client: QdrantClient,
    collection: str,
    embedder: Embedder,
    sparse: SparseEmbedder,
    reranker: Reranker,
    graph: EdgeGraph,
) -> KnowledgeBase:
    return KnowledgeBase(
        client,
        collection,
        embedder,
        sparse,
        reranker,
        graph,
        candidates=settings.retrieval_candidates,
        min_score=settings.rerank_min_score,
        rerank_chars=settings.rerank_max_chars,
    )


def open_knowledge_base(settings: Settings) -> KnowledgeBase:
    """Connect to Qdrant and Postgres and load the local models (slow: run it off the loop).
    Searches go through the alias; the edges are those of the generation it names now."""
    from rag_stack.db.edges import load_edges
    from rag_stack.llm.factory import create_embedder, create_reranker, create_sparse_embedder
    from rag_stack.retrieval.generations import generation_of, serving

    client = QdrantClient(url=settings.qdrant_url)
    alias = settings.qdrant_collection
    generation = generation_of(alias, serving(client, alias) or alias)
    return knowledge_base(
        settings,
        client,
        alias,
        create_embedder(settings.embedding_model),
        create_sparse_embedder(settings.sparse_model),
        create_reranker(settings.reranker_model),
        EdgeGraph(load_edges(settings.database_url, generation)),
    )
