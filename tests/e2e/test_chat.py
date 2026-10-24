"""Question -> answer through the API, against real Qdrant, Postgres, models and LLM.

The fixture corpus is indexed into a throwaway collection, so the real index is untouched."""

import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from rag_stack.api.app import create_app
from rag_stack.config import Settings
from rag_stack.db.edges import EdgeGraph
from rag_stack.ingestion.models import Snapshot
from rag_stack.ingestion.sources import atlas, eu_ai_act
from rag_stack.llm.factory import create_embedder, create_reranker, create_sparse_embedder
from rag_stack.retrieval.index import ensure_collection, index_source
from rag_stack.retrieval.retriever import KnowledgeBase

pytestmark = pytest.mark.e2e
FIXTURES = Path(__file__).parents[1] / "fixtures"


def parse(module, source_id: str, folder: str, names: list[str]):
    files = {n: (FIXTURES / folder / n).read_bytes() for n in names}
    snap = Snapshot(source_id, "fixture", "2026-10-24", files, {n: f"https://x/{n}" for n in files})
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
        eu_ai_act,
        "eu-ai-act",
        "eu_ai_act",
        ["consolidated_en.xhtml", "consolidated_de.xhtml", "oj_en.xhtml", "oj_de.xhtml"],
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
            min_score=settings.rerank_min_score,
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

        off_topic, _ = ask(client, thread_url, "What is the capital of France?")
        assert off_topic.startswith("I can't answer that from the indexed sources.")

    # A fresh app (new connection pool) still sees the conversation in Postgres.
    with TestClient(create_app(retriever=knowledge_base)) as client:
        messages = client.get(thread_url).json()
    assert [m["role"] for m in messages] == ["user", "assistant"] * 4
    assert messages[1]["content"] == first
