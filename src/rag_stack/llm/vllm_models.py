"""Embedding and reranking models served by vLLM (`docker compose --profile gpu`): its
OpenAI-compatible /v1/embeddings and its /v1/rerank."""

from collections.abc import Sequence

import httpx
from openai import OpenAI  # noqa: TID251


class VllmDense:
    def __init__(self, client: OpenAI, model: str, batch_size: int = 32) -> None:
        self._client = client
        self._model = model
        self.name = f"vllm:{model}"
        self._batch_size = batch_size
        self._dim = len(self._embed(["dimension probe"])[0])

    @property
    def dim(self) -> int:
        return self._dim

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        reply = self._client.embeddings.create(model=self._model, input=list(texts))
        return [d.embedding for d in sorted(reply.data, key=lambda d: d.index)]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            vector
            for start in range(0, len(texts), self._batch_size)
            for vector in self._embed(texts[start : start + self._batch_size])
        ]

    def embed_query(self, text: str) -> list[float]:
        # No instruction, though Qwen3-Embedding supports one: on the golden set a cybersecurity
        # instruction dropped KI-MIG § 17 out of the candidates and cost recall@10 (0.968 vs
        # 0.988 without); Qwen's default web-search instruction scored 0.976 (docs/PLAN.md).
        return self._embed([text])[0]


class VllmReranker:
    """Qwen3-Reranker's prompt is applied by the server (`deploy/vllm/qwen3_reranker.jinja`)."""

    def __init__(self, http: httpx.Client, model: str) -> None:
        self._http = http
        self._model = model

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        reply = self._http.post(
            "rerank", json={"model": self._model, "query": query, "documents": list(texts)}
        )
        reply.raise_for_status()
        scores = [0.0] * len(texts)
        for result in reply.json()["results"]:
            scores[result["index"]] = float(result["relevance_score"])
        return scores
