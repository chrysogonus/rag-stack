"""A pack end to end: its sample documents and glossary, indexed into a throwaway
collection, asked through the API against real Qdrant, Postgres, models and LLM."""

import json
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from rag_stack.api.app import create_app
from rag_stack.config import Settings
from rag_stack.db.edges import EdgeGraph
from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Edge, finalize
from rag_stack.ingestion.pipeline import source_config, source_module
from rag_stack.llm.factory import create_embedder, create_reranker, create_sparse_embedder
from rag_stack.retrieval.index import ensure_collection, index_source
from rag_stack.retrieval.retriever import KnowledgeBase

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def served(tmp_path_factory) -> Iterator[tuple[Settings, KnowledgeBase]]:
    settings = Settings(rag_pack="starter")
    pack = settings.pack
    client = QdrantClient(url=settings.qdrant_url)
    collection = f"e2e_{uuid.uuid4().hex[:8]}"
    embedder = create_embedder(
        settings.embedding_model, settings.embedding_provider, settings.embedding_base_url
    )
    sparse = create_sparse_embedder(settings.sparse_model)
    ensure_collection(client, collection, embedder.dim)
    fetcher = Fetcher("e2e", tmp_path_factory.mktemp("cache"), 0)  # the sources are local
    edges: list[Edge] = []
    for source in pack.sources.values():
        module = source_module(source)
        chunks, found = module.parse(
            module.fetch(fetcher, source_config(source, pack), "2026-11-04T00:00:00+00:00")
        )
        chunks = finalize(chunks, settings.max_chunk_chars)
        index_source(
            client, collection, source.id, "e2e", chunks, embedder, sparse, sources=pack.sources
        )
        edges += found
    try:
        yield (
            settings,
            KnowledgeBase(
                client,
                collection,
                embedder,
                sparse,
                create_reranker(
                    settings.reranker_model, settings.reranker_provider, settings.reranker_base_url
                ),
                EdgeGraph(edges),
                pack,
                candidates=settings.retrieval_candidates,
                min_score=settings.rerank_min_score,
                rerank_chars=settings.rerank_max_chars,
            ),
        )
    finally:
        client.delete_collection(collection)


def ask(settings: Settings, kb: KnowledgeBase, question: str) -> tuple[str, list[dict]]:
    with TestClient(create_app(settings, retriever=kb)) as client:
        response = client.post(f"/api/threads/{uuid.uuid4()}/messages", json={"content": question})
    assert response.status_code == 200, response.text
    events = [
        (block.split("\n")[0].removeprefix("event: "), json.loads(block.split("data: ", 1)[1]))
        for block in response.text.strip().split("\n\n")
        if block.startswith("event: ")
    ]
    assert events[-1][0] == "done", events
    sources = next(data["sources"] for kind, data in events if kind == "sources")
    return events[-1][1]["message"]["content"], sources


def test_a_handbook_question_is_answered_from_its_section_and_cites_it(served):
    settings, kb = served
    answer, sources = ask(settings, kb, "How much can I spend on a hotel night in Paris?")

    assert any(s["id"] == "travel-and-expenses.md#hotels" and s["used"] for s in sources)
    assert "220" in answer
    assert "Sample team handbook written for rag-stack, CC0 1.0" in answer
    assert answer.endswith("*AI-generated answer. Check the cited sources.*")


def test_a_question_about_related_terms_follows_the_glossary_links(served):
    settings, kb = served
    answer, sources = ask(settings, kb, "Which glossary terms are related to Expense report?")

    assert any(s["id"] == "Travel desk" for s in sources)
    assert "Travel desk" in answer


def test_a_question_the_handbook_doesnt_answer_is_declined_with_the_packs_hint(served):
    settings, kb = served
    answer, _ = ask(settings, kb, "What is the capital of France?")

    assert answer.startswith("I can't answer that from the indexed sources.")
    assert "such as hotel costs, vacation days or a lost laptop" in answer
    assert "- Team glossary\n- Team handbook\n" in answer


def test_the_page_config_starts_a_question_answered_from_the_source_it_lights_up(served):
    settings, kb = served
    with TestClient(create_app(settings, retriever=kb)) as client:
        config = client.get("/api/config").json()
    first = config["starters"][0]
    assert config["heading"] == "What do you want to know about the team handbook?"

    _, sources = ask(settings, kb, first["question"])

    assert first["source"] in {s["source"] for s in sources if s["used"]}
    assert {s["source"] for s in sources} <= {s["id"] for s in config["sources"]}
