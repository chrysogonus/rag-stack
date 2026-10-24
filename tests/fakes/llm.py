from collections.abc import AsyncIterator, Sequence

from rag_stack.llm.base import Message, TextDelta, Usage


class FakeChatModel:
    """Replays scripted replies word by word, and records every call it gets."""

    def __init__(self, *replies: str, tokens_per_reply: int = 10) -> None:
        self.replies = list(replies)
        self.tokens_per_reply = tokens_per_reply
        self.calls: list[dict] = []

    async def stream(
        self, messages: Sequence[Message], *, instructions: str, max_output_tokens: int
    ) -> AsyncIterator[TextDelta | Usage]:
        self.calls.append(
            {
                "messages": list(messages),
                "instructions": instructions,
                "max_output_tokens": max_output_tokens,
            }
        )
        reply = self.replies.pop(0) if self.replies else "ok"
        for i, word in enumerate(reply.split(" ")):
            yield TextDelta(word if i == 0 else f" {word}")
        yield Usage(self.tokens_per_reply)


class FailingChatModel:
    async def stream(
        self, messages: Sequence[Message], *, instructions: str, max_output_tokens: int
    ) -> AsyncIterator[TextDelta | Usage]:
        yield TextDelta("partial")
        raise RuntimeError("provider down")
