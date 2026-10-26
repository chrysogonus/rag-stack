import json
from types import SimpleNamespace
from typing import Any, cast

import httpx

from rag_stack.llm.vllm_models import QWEN3_QUERY, VllmDense, VllmReranker


class StubClient:
    """The OpenAI SDK's `embeddings.create`, answering out of order (the adapter sorts)."""

    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

        def create(model: str, input: list[str]):
            self.inputs.append(input)
            data = [SimpleNamespace(index=i, embedding=[float(i), 1.0]) for i in range(len(input))]
            return SimpleNamespace(data=data[::-1])

        self.embeddings = SimpleNamespace(create=create)


def test_documents_are_embedded_in_batches_and_only_queries_get_the_instruction():
    client = StubClient()
    model = VllmDense(cast(Any, client), "Qwen/Qwen3-Embedding-4B", batch_size=2)

    assert model.dim == 2
    assert model.embed_documents(["a", "b", "c"]) == [[0.0, 1.0], [1.0, 1.0], [0.0, 1.0]]
    assert model.embed_query("q") == [0.0, 1.0]
    assert client.inputs[1:] == [["a", "b"], ["c"], [QWEN3_QUERY + "q"]]


def test_other_models_get_no_instruction():
    client = StubClient()
    VllmDense(cast(Any, client), "BAAI/bge-m3").embed_query("q")
    assert client.inputs[-1] == ["q"]


def server(reply):
    """An httpx transport that records each JSON request and answers with `reply(body)`."""
    seen: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append({"path": request.url.path, **body})
        return httpx.Response(200, json=reply(body))

    return httpx.MockTransport(handle), seen


def test_rerank_scores_come_back_in_input_order():
    def scores(body: dict) -> dict:
        results = [{"index": i, "relevance_score": i / 10} for i in range(len(body["documents"]))]
        return {"results": sorted(results, key=lambda r: -r["relevance_score"])}

    transport, seen = server(scores)
    http = httpx.Client(base_url="http://gpu/v1/", transport=transport)

    assert VllmReranker(http, "Qwen/Qwen3-Reranker-4B").rerank("q", ["a", "b", "c"]) == [
        0.0,
        0.1,
        0.2,
    ]
    assert seen == [
        {
            "path": "/v1/rerank",
            "model": "Qwen/Qwen3-Reranker-4B",
            "query": "q",
            "documents": ["a", "b", "c"],
        }
    ]
