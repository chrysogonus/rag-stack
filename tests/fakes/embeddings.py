import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence

from rag_stack.ingestion.models import Chunk
from rag_stack.llm.embeddings import SparseVector
from rag_stack.retrieval.retriever import Retrieved


def tokens(text: str) -> list[str]:
    return re.findall(r"[\w.:-]+", text.lower())


def bucket(token: str, size: int) -> int:
    return int(hashlib.sha256(token.encode()).hexdigest(), 16) % size


class FakeEmbedder:
    """Hashed bag of words: texts sharing words are close, deterministically."""

    dim = 64

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in tokens(text):
            vector[bucket(token, self.dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class FakeSparseEmbedder:
    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> SparseVector:
        counts = Counter(bucket(t, 100_000) for t in tokens(text))
        return SparseVector(list(counts), [float(c) for c in counts.values()])


class FakeReranker:
    """Score = number of distinct query words found in the text."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        self.calls.append((query, len(texts)))
        words = set(tokens(query))
        return [float(len(words & set(tokens(t)))) for t in texts]


def chunk(native_id: str, text: str = "text", **fields) -> Chunk:
    defaults = {
        "source_id": "atlas",
        "title": f"Title of {native_id}",
        "url": f"https://example.org/{native_id}",
        "source_version": "2026.09",
        "language": "en",
        "retrieved_at": "2026-10-24T00:00:00+00:00",
        "license": "Apache-2.0",
        "attribution": "MITRE ATLAS™, Copyright 2021-2026 MITRE, Apache-2.0",
    }
    return Chunk(native_id=native_id, text=text, **{**defaults, **fields})


class FakeRetriever:
    """Returns the scripted chunks for every question and records what it was asked."""

    def __init__(self, *chunks: Chunk, catalog: Sequence[str] = ("MITRE ATLAS 2026.09",)):
        self.chunks = list(chunks)
        self.calls: list[tuple[str, str]] = []
        self._catalog = list(catalog)

    async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
        self.calls.append((query, context))
        return [Retrieved(c, 1.0, "hybrid") for c in self.chunks]

    async def catalog(self) -> list[str]:
        return self._catalog
