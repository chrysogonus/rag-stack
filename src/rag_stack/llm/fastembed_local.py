"""Open-weights embedding and reranking models run locally with fastembed (ONNX, no torch).

fastembed is imported when a model is constructed, so unit tests never load it."""

from collections.abc import Sequence
from typing import Any

from rag_stack.llm.embeddings import SparseVector


class FastembedDense:
    def __init__(self, model: str) -> None:
        from fastembed import TextEmbedding  # noqa: TID251

        self._model = TextEmbedding(model)
        self.name = f"fastembed:{model}"
        # e5 models are trained with these prefixes and fastembed doesn't add them.
        self._prefixes = ("query: ", "passage: ") if "e5" in model else ("", "")
        self._dim = len(next(iter(self._model.embed(["dimension probe"]))))

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        prefixed = [self._prefixes[1] + t for t in texts]
        return [v.tolist() for v in self._model.embed(prefixed, batch_size=16)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.embed([self._prefixes[0] + text]))).tolist()


class FastembedSparse:
    def __init__(self, model: str) -> None:
        from fastembed import SparseTextEmbedding  # noqa: TID251

        # The corpus mixes English and German, so no (English) stemming.
        options: dict[str, Any] = {"disable_stemmer": True} if model == "Qdrant/bm25" else {}
        self._model = SparseTextEmbedding(model, **options)

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [
            SparseVector(v.indices.tolist(), v.values.tolist()) for v in self._model.embed(texts)
        ]

    def embed_query(self, text: str) -> SparseVector:
        v = next(iter(self._model.query_embed(text)))
        return SparseVector(v.indices.tolist(), v.values.tolist())


class FastembedReranker:
    def __init__(self, model: str) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # noqa: TID251

        self._model = TextCrossEncoder(model)

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, list(texts), batch_size=16)]
