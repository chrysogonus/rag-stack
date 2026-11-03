import re
from collections.abc import Sequence

from rag_stack.ingestion.models import Chunk
from rag_stack.llm.base import Message

ABSTAIN = "I can't answer that from the indexed sources."

# The system and baseline prompts are the pack's (packs/<name>/prompts/).


def build_input(history: Sequence[Message], max_messages: int) -> list[Message]:
    """Keep the most recent messages, starting on a user turn."""
    recent = list(history[-max_messages:])
    while recent and recent[0]["role"] != "user":
        recent.pop(0)
    return recent


def escape(text: str) -> str:
    """Neutralize tags in source text that could close or open a source block."""
    return re.sub(r"<(\s*/?\s*source)", r"‹\1", text, flags=re.IGNORECASE)


def build_sources_block(chunks: Sequence[Chunk], max_chars: int) -> str:
    blocks = []
    for n, chunk in enumerate(chunks, start=1):
        heading = " > ".join(chunk.heading_path)
        title = escape(chunk.title).replace('"', "'")
        attrs = f'n="{n}" id="{chunk.native_id}" url="{chunk.url}" title="{title}"'
        attrs += f' language="{chunk.language}"'
        if relation := chunk.meta.get("relation"):
            attrs += f' relation="{relation}"'
        body = escape(chunk.text[:max_chars])
        blocks.append(f"<source {attrs}>\n{escape(heading)}\n{body}\n</source>")
    return "\n\n".join(blocks)


def with_sources(messages: list[Message], chunks: Sequence[Chunk], max_chars: int) -> list[Message]:
    """Put the sources into the latest user turn, ahead of the question."""
    *history, question = messages
    content = (
        f"Sources:\n\n{build_sources_block(chunks, max_chars)}\n\nQuestion: {question['content']}"
    )
    return [*history, {"role": "user", "content": content}]
