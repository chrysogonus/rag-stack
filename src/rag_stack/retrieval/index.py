from collections.abc import Iterator, Sequence
from typing import cast

from qdrant_client import QdrantClient, models

from rag_stack.config import Settings
from rag_stack.ingestion.models import Chunk
from rag_stack.ingestion.registry import SOURCES
from rag_stack.llm.embeddings import Embedder, SparseEmbedder

# Points indexed before `embedding_model` was stored all came from this model.
LEGACY_EMBEDDING = "fastembed:intfloat/multilingual-e5-large"
KEYWORD_FIELDS = (
    "native_id",
    "parent_ids",
    "aliases",
    "source_id",
    "language",
    "unit_key",
    "catalog",
    "processed_sha",
)


def catalog_label(chunk: Chunk) -> str:
    """How a source and its version are named to users, e.g. 'MITRE ATLAS 2026.09'. A retired
    source has no registry entry but stays served until the next refresh drops it."""
    source = SOURCES.get(chunk.source_id)
    return f"{source.name if source else chunk.source_id} {chunk.source_version}"


def ensure_collection(client: QdrantClient, collection: str, dim: int) -> None:
    if client.collection_exists(collection):
        return
    client.create_collection(
        collection,
        vectors_config={"dense": models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    for field in KEYWORD_FIELDS:
        client.create_payload_index(collection, field, models.PayloadSchemaType.KEYWORD)


def match(key: str, value: str) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def index_source(
    client: QdrantClient,
    collection: str,
    source_id: str,
    sha: str,
    chunks: Sequence[Chunk],
    embedder: Embedder,
    sparse: SparseEmbedder,
    batch_size: int = 64,
    reuse_from: str | None = None,
) -> str:
    """Replace a source's points, unless they already come from this processed snapshot. With
    `reuse_from`, a chunk whose point in that collection embedded the same text keeps its
    vectors, so only new and changed chunks are embedded."""
    current = models.Filter(must=[match("source_id", source_id), match("processed_sha", sha)])
    if client.count(collection, count_filter=current, exact=True).count == len(chunks):
        return f"{source_id}: unchanged, {len(chunks)} chunks already indexed"
    every = models.Filter(must=[match("source_id", source_id)])
    client.delete(collection, points_selector=models.FilterSelector(filter=every))
    embedded = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = reusable(client, reuse_from, batch, embedder.name) if reuse_from else {}
        fresh = [c for c in batch if c.point_id not in vectors]
        if fresh:
            texts = [c.embedding_text() for c in fresh]
            for chunk, d, s in zip(
                fresh, embedder.embed_documents(texts), sparse.embed_documents(texts), strict=True
            ):
                vectors[chunk.point_id] = {
                    "dense": d,
                    "bm25": models.SparseVector(indices=s.indices, values=s.values),
                }
            embedded += len(fresh)
        client.upsert(
            collection,
            [
                models.PointStruct(
                    id=chunk.point_id,
                    vector=vectors[chunk.point_id],
                    payload={
                        **chunk.model_dump(),
                        "catalog": catalog_label(chunk),
                        "processed_sha": sha,
                        "embedding_model": embedder.name,
                    },
                )
                for chunk in batch
            ],
        )
    reused = f", {len(chunks) - embedded} with reused vectors" if reuse_from else ""
    return f"{source_id}: indexed {len(chunks)} chunks{reused}"


def reusable(
    client: QdrantClient, collection: str, chunks: Sequence[Chunk], embedding: str
) -> dict[str, models.VectorStruct]:
    """The vectors of the chunks whose point in `collection` embedded the same text with the
    same model: a new source version or other metadata alone changes no vector."""
    found = client.retrieve(
        collection, [c.point_id for c in chunks], with_payload=True, with_vectors=True
    )
    texts = {c.point_id: c.embedding_text() for c in chunks}
    return {
        str(r.id): cast(models.VectorStruct, r.vector)
        for r in found
        if r.payload
        and r.payload.get("embedding_model", LEGACY_EMBEDDING) == embedding
        and Chunk.model_validate(r.payload).embedding_text() == texts[str(r.id)]
    }


def embedding_in(client: QdrantClient, collection: str) -> str | None:
    """The embedding model of a collection's vectors (None when it is empty)."""
    records, _ = client.scroll(collection, limit=1, with_payload=["embedding_model"])
    return (records[0].payload or {}).get("embedding_model", LEGACY_EMBEDDING) if records else None


def index_all(settings: Settings, source: str = "all") -> Iterator[str]:
    """Index in place into the served generation, without the checks of `make refresh`."""
    from rag_stack.db.edges import replace_edges
    from rag_stack.ingestion.pipeline import MODULES, load_processed
    from rag_stack.llm.factory import create_embedder, create_sparse_embedder
    from rag_stack.retrieval.generations import (
        collection_name,
        generation_of,
        new_generation,
        promote,
        serving,
    )

    embedder = create_embedder(
        settings.embedding_model, settings.embedding_provider, settings.embedding_base_url
    )
    sparse = create_sparse_embedder(settings.sparse_model)
    client = QdrantClient(url=settings.qdrant_url)
    alias = settings.qdrant_collection
    if (collection := serving(client, alias)) is None:
        collection = collection_name(alias, new_generation())
        ensure_collection(client, collection, embedder.dim)
        promote(client, alias, collection)
    if (served_model := embedding_in(client, collection)) not in (None, embedder.name):
        raise ValueError(
            f"{collection} holds {served_model} vectors, not {embedder.name}: "
            "`make refresh` builds a new index for a new embedding model"
        )
    generation = generation_of(alias, collection)
    for source_id in MODULES if source == "all" else [source]:
        processed = load_processed(settings, source_id)
        if processed is None:
            yield f"{source_id}: nothing to index, run `make ingest SOURCE={source_id}` first"
            continue
        sha, chunks, edges = processed
        yield index_source(client, collection, source_id, sha, chunks, embedder, sparse)
        replace_edges(settings.database_url, generation, source_id, edges)
        yield f"{source_id}: {len(edges)} edges"
