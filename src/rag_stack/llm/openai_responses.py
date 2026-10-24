from collections.abc import AsyncIterator, Sequence

from openai import AsyncOpenAI  # noqa: TID251

from rag_stack.llm.base import Message, TextDelta, Usage


class OpenAIResponsesModel:
    """OpenAI's Responses API."""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def stream(
        self, messages: Sequence[Message], *, instructions: str, max_output_tokens: int
    ) -> AsyncIterator[TextDelta | Usage]:
        async with self._client.responses.stream(
            model=self._model,
            instructions=instructions,
            input=[{"role": m["role"], "content": m["content"]} for m in messages],
            max_output_tokens=max_output_tokens,
            store=False,
        ) as stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield TextDelta(event.delta)
            response = await stream.get_final_response()
        yield Usage(response.usage.total_tokens if response.usage else 0)
