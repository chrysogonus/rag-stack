from types import SimpleNamespace
from typing import Any, cast

import pytest

from rag_stack.llm.anthropic_messages import AnthropicModel
from rag_stack.llm.base import TextDelta, Usage

pytestmark = pytest.mark.anyio


class StubStream:
    def __init__(self, texts: list[str]) -> None:
        self.texts = texts

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    async def text_stream(self):
        for text in self.texts:
            yield text

    async def get_final_message(self):
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=30, output_tokens=12))


class StubClient:
    def __init__(self, stream: StubStream) -> None:
        self.kwargs: dict[str, Any] = {}

        def make_stream(**kwargs):
            self.kwargs = kwargs
            return stream

        self.messages = SimpleNamespace(stream=make_stream)


async def test_streams_text_then_input_plus_output_usage():
    client = StubClient(StubStream(["Hel", "lo"]))
    model = AnthropicModel(cast(Any, client), "claude-sonnet-5-5")

    out = [
        e
        async for e in model.stream(
            [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hey"}],
            instructions="Be nice.",
            max_output_tokens=50,
        )
    ]

    assert out == [TextDelta("Hel"), TextDelta("lo"), Usage(42)]
    assert client.kwargs == {
        "model": "claude-sonnet-5-5",
        "system": "Be nice.",
        "messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hey"}],
        "max_tokens": 50,
    }
