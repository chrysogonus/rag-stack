from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SparseVector:
    indices: list[int]
    values: list[float]


class Embedder(Protocol):
    """Dense text embeddings. Documents and queries may be encoded differently."""

    @property
    def dim(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SparseEmbedder(Protocol):
    """Sparse lexical vectors (BM25 term weights; IDF is applied by the vector store)."""

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]: ...

    def embed_query(self, text: str) -> SparseVector: ...


class Reranker(Protocol):
    """Cross-encoder relevance scores, one per text, higher is more relevant."""

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]: ...
