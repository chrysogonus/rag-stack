from collections.abc import Iterator, Sequence

from qdrant_client import QdrantClient, models

from rag_stack.config import Settings
from rag_stack.ingestion.models import Chunk
from rag_stack.ingestion.registry import SOURCES
from rag_stack.llm.embeddings import Embedder, SparseEmbedder

KEYWORD_FIELDS = (
    "native_id",
    "parent_ids",
    "aliases",
    "source_id",
    "language",
    "unit_key",
    "catalog",
)


def catalog_label(chunk: Chunk) -> str:
    """How a source and its version are named to users, e.g. 'MITRE ATLAS 2026.09'."""
    return f"{SOURCES[chunk.source_id].name} {chunk.source_version}"


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
) -> str:
    """Replace a source's points, unless they already come from this processed snapshot."""
    current = models.Filter(must=[match("source_id", source_id), match("processed_sha", sha)])
    if client.count(collection, count_filter=current, exact=True).count == len(chunks):
        return f"{source_id}: unchanged, {len(chunks)} chunks already indexed"
    every = models.Filter(must=[match("source_id", source_id)])
    client.delete(collection, points_selector=models.FilterSelector(filter=every))
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c.embedding_text() for c in batch]
        dense = embedder.embed_documents(texts)
        lexical = sparse.embed_documents(texts)
        client.upsert(
            collection,
            [
                models.PointStruct(
                    id=chunk.point_id,
                    vector={
                        "dense": d,
                        "bm25": models.SparseVector(indices=s.indices, values=s.values),
                    },
                    payload={
                        **chunk.model_dump(),
                        "catalog": catalog_label(chunk),
                        "processed_sha": sha,
                    },
                )
                for chunk, d, s in zip(batch, dense, lexical, strict=True)
            ],
        )
    return f"{source_id}: indexed {len(chunks)} chunks"


def index_all(settings: Settings, source: str = "all") -> Iterator[str]:
    from rag_stack.db.edges import replace_edges
    from rag_stack.ingestion.pipeline import MODULES, load_processed
    from rag_stack.llm.factory import create_embedder, create_sparse_embedder

    embedder = create_embedder(settings.embedding_model)
    sparse = create_sparse_embedder(settings.sparse_model)
    client = QdrantClient(url=settings.qdrant_url)
    ensure_collection(client, settings.qdrant_collection, embedder.dim)
    for source_id in MODULES if source == "all" else [source]:
        processed = load_processed(settings, source_id)
        if processed is None:
            yield f"{source_id}: nothing to index, run `make ingest SOURCE={source_id}` first"
            continue
        sha, chunks, edges = processed
        yield index_source(
            client, settings.qdrant_collection, source_id, sha, chunks, embedder, sparse
        )
        replace_edges(settings.database_url, source_id, edges)
        yield f"{source_id}: {len(edges)} edges"
