from types import SimpleNamespace
from typing import Any, cast

import pytest

from rag_stack.llm.base import TextDelta, Usage
from rag_stack.llm.openai_responses import OpenAIResponsesModel

pytestmark = pytest.mark.anyio


class StubStream:
    def __init__(self, events: list[SimpleNamespace], total_tokens: int) -> None:
        self.events = events
        self.total_tokens = total_tokens

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def __aiter__(self):
        for event in self.events:
            yield event

    async def get_final_response(self):
        return SimpleNamespace(usage=SimpleNamespace(total_tokens=self.total_tokens))


class StubClient:
    def __init__(self, stream: StubStream) -> None:
        self.kwargs: dict[str, Any] = {}

        def make_stream(**kwargs):
            self.kwargs = kwargs
            return stream

        self.responses = SimpleNamespace(stream=make_stream)


async def test_maps_text_deltas_and_final_usage():
    events = [
        SimpleNamespace(type="response.created"),
        SimpleNamespace(type="response.output_text.delta", delta="Hel"),
        SimpleNamespace(type="response.reasoning_summary_text.delta", delta="thinking"),
        SimpleNamespace(type="response.output_text.delta", delta="lo"),
        SimpleNamespace(type="response.completed"),
    ]
    client = StubClient(StubStream(events, total_tokens=7))
    model = OpenAIResponsesModel(cast(Any, client), "gpt-6-astra")

    out = [
        e
        async for e in model.stream(
            [{"role": "user", "content": "Hi"}], instructions="Be nice.", max_output_tokens=50
        )
    ]

    assert out == [TextDelta("Hel"), TextDelta("lo"), Usage(7)]
    assert client.kwargs == {
        "model": "gpt-6-astra",
        "instructions": "Be nice.",
        "input": [{"role": "user", "content": "Hi"}],
        "max_output_tokens": 50,
        "store": False,
    }
