from collections.abc import Sequence

from rag_stack.llm.base import Message

SYSTEM_PROMPT = """\
You are the knowledge base assistant. Answer the user's question helpfully, accurately and \
concisely. If you don't know the answer, say so instead of guessing. Use Markdown when it makes \
the answer easier to read."""


def build_input(history: Sequence[Message], max_messages: int) -> list[Message]:
    """Keep the most recent messages, starting on a user turn."""
    recent = list(history[-max_messages:])
    while recent and recent[0]["role"] != "user":
        recent.pop(0)
    return recent
