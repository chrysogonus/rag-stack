import json
import time
import uuid
from collections.abc import Iterator

import anyio
import pytest
from fakes.embeddings import FakeRetriever, chunk
from fakes.llm import FailingChatModel, FakeChatModel
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from rag_stack.agent.answer import footer
from rag_stack.api.app import create_app, source_refs
from rag_stack.config import Settings
from rag_stack.llm.base import ChatModel, TextDelta


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def make_client() -> Iterator:
    clients: list[TestClient] = []

    def make(llm: ChatModel | None = None, **settings) -> TestClient:
        app = create_app(
            Settings(**settings), llm or FakeChatModel(), InMemorySaver(), FakeRetriever(SOURCE)
        )
        client = TestClient(app).__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


SOURCE = chunk("AML.T0051", "LLM Prompt Injection")
FOOTER = footer("Hello there", [SOURCE], "en")
SOURCE_REF = {
    "id": "AML.T0051",
    "title": "Title of AML.T0051",
    "source": "atlas",
    "url": "https://example.org/AML.T0051",
    "used": True,
}


def url() -> str:
    return f"/api/threads/{uuid.uuid4()}/messages"


def test_post_streams_deltas_then_the_final_message(make_client):
    client = make_client(FakeChatModel("Hello there"))

    response = client.post(url(), json={"content": "Hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(response.text) == [
        ("sources", {"sources": [SOURCE_REF]}),
        ("delta", {"text": "Hello"}),
        ("delta", {"text": " there"}),
        ("delta", {"text": FOOTER}),
        ("done", {"message": {"role": "assistant", "content": "Hello there" + FOOTER}}),
    ]


def test_sources_event_lists_each_passage_once_and_marks_the_ones_answered_from():
    ranked = [
        chunk("AML.T0051", chunk_index=0),
        chunk("AML.T0051", chunk_index=1),
        chunk("LLM01", source_id="owasp-llm-2026"),
        chunk("AML.T0051", chunk_index=2),
        chunk("AML.M0019"),
    ]

    refs = source_refs([c.model_dump() for c in ranked], top_k=3)

    assert [(r["id"], r["source"], r["used"]) for r in refs] == [
        ("AML.T0051", "atlas", True),
        ("LLM01", "owasp-llm-2026", True),
        ("AML.M0019", "atlas", False),
    ]
    assert "text" not in refs[0]


def test_get_returns_the_conversation(make_client):
    client = make_client(FakeChatModel("Hello there"))
    thread = url()

    assert client.get(thread).json() == []
    client.post(thread, json={"content": "  Hi  "})

    assert client.get(thread).json() == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello there" + FOOTER},
    ]


@pytest.mark.parametrize("content", ["", "   ", "x" * 11])
def test_rejects_empty_or_oversized_input(make_client, content):
    client = make_client(max_input_chars=10)

    assert client.post(url(), json={"content": content}).status_code == 422


def test_rejects_thread_ids_that_are_not_uuids(make_client):
    client = make_client()

    assert client.get("/api/threads/abc/messages").status_code == 422
    assert client.post("/api/threads/abc/messages", json={"content": "Hi"}).status_code == 422


def test_rate_limit_returns_429(make_client):
    client = make_client(rate_limit_per_minute=1)

    assert client.post(url(), json={"content": "Hi"}).status_code == 200
    response = client.post(url(), json={"content": "Hi"})
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]


def test_daily_token_budget_returns_429(make_client):
    client = make_client(FakeChatModel(tokens_per_reply=10), daily_token_budget_per_client=10)

    assert client.post(url(), json={"content": "Hi"}).status_code == 200
    response = client.post(url(), json={"content": "Hi"})
    assert response.status_code == 429
    assert "Daily usage limit" in response.json()["detail"]


def test_full_thread_returns_409(make_client):
    client = make_client(max_turns_per_thread=1)
    thread = url()

    assert client.post(thread, json={"content": "Hi"}).status_code == 200
    assert client.post(thread, json={"content": "Again"}).status_code == 409
    assert client.post(url(), json={"content": "New chat"}).status_code == 200


def test_llm_failure_ends_the_stream_with_a_generic_error(make_client):
    client = make_client(FailingChatModel())

    response = client.post(url(), json={"content": "Hi"})

    assert response.status_code == 200
    assert parse_sse(response.text) == [
        ("sources", {"sources": [SOURCE_REF]}),
        ("delta", {"text": "partial"}),
        ("error", {"detail": "Something went wrong. Please try again."}),
    ]


def test_a_failed_answer_is_kept_marked_as_stopped(make_client):
    client = make_client(FailingChatModel())
    thread = url()
    client.post(thread, json={"content": "Hi"})

    assert client.get(thread).json() == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "partial\n\n_Stopped._"},
    ]


class StallingChatModel:
    """Streams one word, then waits until the client goes away."""

    async def stream(self, messages, *, instructions, max_output_tokens):
        yield TextDelta("Partial")
        await anyio.sleep(30)
        yield TextDelta(" never sent")


def test_an_answer_cut_off_by_the_client_is_kept_marked_as_stopped(make_client):
    client = make_client(StallingChatModel())
    thread = url()

    with client.stream("POST", thread, json={"content": "Hi"}) as response:
        for line in response.iter_lines():
            if line.startswith("event: delta"):
                break

    messages: list[dict] = []
    for _ in range(50):  # the save runs as the server notices the disconnect
        messages = client.get(thread).json()
        if len(messages) == 2:
            break
        time.sleep(0.05)
    assert messages == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Partial\n\n_Stopped._"},
    ]
