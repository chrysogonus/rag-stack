from collections.abc import AsyncIterator, Sequence

from openai import AsyncOpenAI  # noqa: TID251
from openai.types.chat import ChatCompletionMessageParam  # noqa: TID251

from rag_stack.llm.base import Message, TextDelta, Usage


class OpenAICompatibleModel:
    """Any server that speaks OpenAI's Chat Completions API: Ollama, vLLM, LM Studio, gateways."""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def stream(
        self, messages: Sequence[Message], *, instructions: str, max_output_tokens: int
    ) -> AsyncIterator[TextDelta | Usage]:
        prompt: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": instructions},
            *(
                {"role": "user", "content": m["content"]}
                if m["role"] == "user"
                else {"role": "assistant", "content": m["content"]}
                for m in messages
            ),
        ]
        chunks = await self._client.chat.completions.create(
            model=self._model,
            messages=prompt,
            max_tokens=max_output_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        output_chars = 0
        total_tokens = None
        async for chunk in chunks:
            if chunk.usage:
                total_tokens = chunk.usage.total_tokens
            if chunk.choices and chunk.choices[0].delta.content:
                output_chars += len(chunk.choices[0].delta.content)
                yield TextDelta(chunk.choices[0].delta.content)
        if total_tokens is None:
            # ponytail: ~4 characters per token, for servers that don't report usage when
            # streaming, so the daily token budget still applies. Use a tokenizer for exact counts.
            input_chars = len(instructions) + sum(len(m["content"]) for m in messages)
            total_tokens = (input_chars + output_chars) // 4
        yield Usage(total_tokens)
