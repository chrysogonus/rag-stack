from types import SimpleNamespace
from typing import Any, cast

import pytest

from rag_stack.llm.base import Message, TextDelta, Usage
from rag_stack.llm.openai_compatible import OpenAICompatibleModel

pytestmark = pytest.mark.anyio


def chunk(content: str | None = None, usage: int | None = None, choices: bool = True):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))] if choices else [],
        usage=SimpleNamespace(total_tokens=usage) if usage is not None else None,
    )


class StubClient:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self.kwargs: dict[str, Any] = {}

        async def stream():
            for c in chunks:
                yield c

        async def create(**kwargs):
            self.kwargs = kwargs
            return stream()

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


async def run(client: StubClient, messages: list[Message], instructions: str = "Be nice.") -> list:
    model = OpenAICompatibleModel(cast(Any, client), "llama3.3")
    stream = model.stream(messages, instructions=instructions, max_output_tokens=50)
    return [e async for e in stream]


async def test_sends_instructions_as_system_message_with_the_conversation():
    client = StubClient([chunk("ok"), chunk(choices=False, usage=3)])
    history: list[Message] = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Bye"},
    ]

    await run(client, history)

    assert client.kwargs == {
        "model": "llama3.3",
        "messages": [{"role": "system", "content": "Be nice."}, *history],
        "max_tokens": 50,
        "stream": True,
        "stream_options": {"include_usage": True},
    }


async def test_maps_chunks_to_deltas_and_reports_server_usage():
    client = StubClient(
        [chunk(""), chunk("Hel"), chunk(None), chunk("lo"), chunk(choices=False, usage=42)]
    )

    out = await run(client, [{"role": "user", "content": "Hi"}])

    assert out == [TextDelta("Hel"), TextDelta("lo"), Usage(42)]


async def test_estimates_usage_when_the_server_reports_none():
    client = StubClient([chunk("abcd" * 3)])  # 12 output characters

    out = await run(client, [{"role": "user", "content": "x" * 20}], instructions="y" * 8)

    assert out == [TextDelta("abcd" * 3), Usage((8 + 20 + 12) // 4)]
