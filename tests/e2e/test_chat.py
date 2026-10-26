"""Question -> answer through the API, against real Qdrant, Postgres, models and LLM.

The fixture corpus is indexed into a throwaway collection, so the real index is untouched."""

import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from rag_stack import observability
from rag_stack.api.app import create_app
from rag_stack.config import Settings
from rag_stack.db.edges import EdgeGraph
from rag_stack.ingestion.models import Snapshot
from rag_stack.ingestion.sources import atlas, eu_law
from rag_stack.llm.factory import create_embedder, create_reranker, create_sparse_embedder
from rag_stack.retrieval.index import ensure_collection, index_source
from rag_stack.retrieval.retriever import KnowledgeBase

pytestmark = pytest.mark.e2e
FIXTURES = Path(__file__).parents[1] / "fixtures"


def parse(module, source_id: str, folder: str, names: list[str], version: str = "fixture"):
    files = {n: (FIXTURES / folder / n).read_bytes() for n in names}
    snap = Snapshot(source_id, version, "2026-10-24", files, {n: f"https://x/{n}" for n in files})
    return module.parse(snap)


@pytest.fixture(scope="module")
def knowledge_base() -> Iterator[KnowledgeBase]:
    settings = Settings()
    client = QdrantClient(url=settings.qdrant_url)
    collection = f"e2e_{uuid.uuid4().hex[:8]}"
    embedder = create_embedder(settings.embedding_model)
    sparse = create_sparse_embedder(settings.sparse_model)
    ensure_collection(client, collection, embedder.dim)
    atlas_chunks, edges = parse(atlas, "atlas", "atlas", ["ATLAS.yaml"])
    act_chunks, _ = parse(
        eu_law,
        "eu-ai-act",
        "eu_ai_act",
        ["consolidated_en.xhtml", "consolidated_de.xhtml", "oj_en.xhtml", "oj_de.xhtml"],
        "02024R1689-20260727",
    )
    index_source(client, collection, "atlas", "e2e", atlas_chunks, embedder, sparse)
    index_source(client, collection, "eu-ai-act", "e2e", act_chunks, embedder, sparse)
    try:
        yield KnowledgeBase(
            client,
            collection,
            embedder,
            sparse,
            create_reranker(settings.reranker_model),
            EdgeGraph(edges),
            candidates=settings.retrieval_candidates,
            min_score=settings.rerank_min_score,
            rerank_chars=settings.rerank_max_chars,
        )
    finally:
        client.delete_collection(collection)


def ask(client: TestClient, thread_url: str, question: str) -> tuple[str, list[dict]]:
    response = client.post(thread_url, json={"content": question})
    assert response.status_code == 200, response.text
    events = [
        (block.split("\n")[0].removeprefix("event: "), json.loads(block.split("data: ", 1)[1]))
        for block in response.text.strip().split("\n\n")
        if block.startswith("event: ")
    ]
    kinds = [kind for kind, _ in events]
    assert "error" not in kinds, events
    assert kinds[-1] == "done" and "delta" in kinds
    # The UI lights up the retrieved passages before the answer starts.
    assert kinds.index("sources") < kinds.index("delta")
    streamed = "".join(data["text"] for kind, data in events if kind == "delta")
    final = events[-1][1]["message"]["content"]
    assert streamed == final
    sources = next(data["sources"] for kind, data in events if kind == "sources")
    return final, sources


def test_cited_multi_turn_answers_are_streamed_and_persisted(knowledge_base):
    thread_url = f"/api/threads/{uuid.uuid4()}/messages"

    with TestClient(create_app(retriever=knowledge_base)) as client:
        first, sources = ask(client, thread_url, "What is AML.T0051?")
        assert any(s["id"] == "AML.T0051" and s["source"] == "atlas" and s["used"] for s in sources)
        assert "[AML.T0051]" in first
        assert "**Sources**" in first and "Copyright 2021-2026 MITRE" in first
        assert "AI-generated answer (EU AI Act Art. 50(1))" in first

        follow_up, _ = ask(client, thread_url, "Which mitigations address it?")
        assert "AML.M0019" in follow_up

        german, _ = ask(client, thread_url, "Was verlangt Art. 50 Abs. 1 von Anbietern?")
        assert "[AI Act Art. 50(1)]" in german
        assert "Die Anbieter stellen sicher" in german or "natürliche" in german
        assert "KI-generierte Antwort" in german

        tactics, _ = ask(client, thread_url, "Which tactics does MITRE ATLAS define?")
        assert "[ATLAS Tactics]" in tactics and "Execution" in tactics

        off_topic, _ = ask(client, thread_url, "What is the capital of France?")
        assert off_topic.startswith("I can't answer that from the indexed sources.")
        assert "Try naming what you're asking about" in off_topic
        # Each indexed source once, by name, without version strings.
        assert "- EU AI Act (Regulation (EU) 2024/1689)\n- MITRE ATLAS\n" in off_topic
        assert "02024R1689" not in off_topic and "2026.09" not in off_topic

    # A fresh app (new connection pool) still sees the conversation in Postgres.
    with TestClient(create_app(retriever=knowledge_base)) as client:
        messages = client.get(thread_url).json()
    assert [m["role"] for m in messages] == ["user", "assistant"] * 5
    assert messages[1]["content"] == first
    assert messages[-1]["content"] == off_topic


def test_a_follow_up_asking_how_to_defend_gets_the_mitigations(knowledge_base):
    thread_url = f"/api/threads/{uuid.uuid4()}/messages"

    with TestClient(create_app(retriever=knowledge_base)) as client:
        ask(client, thread_url, "What is AML.T0051?")
        answer, sources = ask(client, thread_url, "How do I defend against it?")

    assert any(s["id"] == "AML.M0019" and s["used"] for s in sources)
    assert not answer.startswith("I can't answer that")
    assert "AML.M0019" in answer


def test_an_answer_cut_off_by_the_client_is_kept_and_the_chat_goes_on(knowledge_base):
    thread_url = f"/api/threads/{uuid.uuid4()}/messages"

    with TestClient(create_app(retriever=knowledge_base)) as client:
        with client.stream("POST", thread_url, json={"content": "What is AML.T0051?"}) as response:
            for line in response.iter_lines():
                if line.startswith("event: delta"):
                    break
        messages: list[dict] = []
        for _ in range(100):  # the server saves the partial answer as it notices the disconnect
            messages = client.get(thread_url).json()
            if len(messages) == 2:
                break
            time.sleep(0.1)
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"].endswith("_Stopped._")

        follow_up, _ = ask(client, thread_url, "Which mitigations address it?")
        assert "AML.M0019" in follow_up
        assert [m["role"] for m in client.get(thread_url).json()] == ["user", "assistant"] * 2


def test_a_rated_answer_reaches_langfuse_as_one_trace_with_its_score(knowledge_base):
    settings = Settings()
    if not settings.langfuse_public_key:
        pytest.skip("tracing is not configured: run `make tracing` and set LANGFUSE_* in .env")
    thread = uuid.uuid4()

    with TestClient(create_app(retriever=knowledge_base)) as client:
        ask(client, f"/api/threads/{thread}/messages", "What is AML.T0051?")
        rating = {"message": 1, "helpful": False}
        assert client.post(f"/api/threads/{thread}/feedback", json=rating).status_code == 204

    trace = observability.turn_trace_id(str(thread), 1)
    auth = (settings.langfuse_public_key, settings.langfuse_secret_key.get_secret_value())
    api = f"{settings.langfuse_base_url}/api/public"
    names: set[str] = set()
    scores: list[dict] = []
    for _ in range(60):  # Langfuse ingests asynchronously
        observations = httpx.get(f"{api}/v2/observations", params={"traceId": trace}, auth=auth)
        names = {o["name"] for o in observations.json()["data"]}
        scores = httpx.get(f"{api}/v3/scores", params={"traceId": trace}, auth=auth).json()["data"]
        if {"retrieve", "rerank", "generate"} <= names and scores:
            break
        time.sleep(1)
    assert {"retrieve", "hybrid search", "rerank", "generate"} <= names
    assert [(s["name"], s["value"]) for s in scores] == [("helpful", False)]
