from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Usage:
    total_tokens: int


class ChatModel(Protocol):
    def stream(
        self, messages: Sequence[Message], *, instructions: str, max_output_tokens: int
    ) -> AsyncIterator[TextDelta | Usage]:
        """Stream the reply as text deltas, then one final Usage."""
        ...
