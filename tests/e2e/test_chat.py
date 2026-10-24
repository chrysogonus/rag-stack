import json
import uuid

import pytest
from fastapi.testclient import TestClient

from rag_stack.api.app import create_app

pytestmark = pytest.mark.e2e


def ask(client: TestClient, thread_url: str, question: str) -> str:
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
    streamed = "".join(data["text"] for kind, data in events if kind == "delta")
    final = events[-1][1]["message"]["content"]
    assert streamed == final
    return final


def test_multi_turn_conversation_is_answered_and_persisted():
    thread_url = f"/api/threads/{uuid.uuid4()}/messages"

    with TestClient(create_app()) as client:
        first = ask(client, thread_url, "What is the capital of Italy? Answer in one word.")
        assert "rome" in first.lower()
        follow_up = ask(client, thread_url, "Which river flows through it? Answer in one word.")
        assert "tiber" in follow_up.lower() or "tevere" in follow_up.lower()

    # A fresh app (new connection pool) still sees the conversation in Postgres.
    with TestClient(create_app()) as client:
        messages = client.get(thread_url).json()

    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1]["content"] == first
    assert messages[3]["content"] == follow_up
