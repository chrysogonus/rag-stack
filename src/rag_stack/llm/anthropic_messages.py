from collections.abc import AsyncIterator, Sequence

from anthropic import AsyncAnthropic  # noqa: TID251
from anthropic.types import MessageParam  # noqa: TID251

from rag_stack.llm.base import Message, TextDelta, Usage


class AnthropicModel:
    """Anthropic's Messages API."""

    def __init__(self, client: AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def stream(
        self, messages: Sequence[Message], *, instructions: str, max_output_tokens: int
    ) -> AsyncIterator[TextDelta | Usage]:
        turns: list[MessageParam] = [
            {"role": "user", "content": m["content"]}
            if m["role"] == "user"
            else {"role": "assistant", "content": m["content"]}
            for m in messages
        ]
        async with self._client.messages.stream(
            model=self._model,
            system=instructions,
            messages=turns,
            max_tokens=max_output_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield TextDelta(text)
            usage = (await stream.get_final_message()).usage
        yield Usage(usage.input_tokens + usage.output_tokens)
