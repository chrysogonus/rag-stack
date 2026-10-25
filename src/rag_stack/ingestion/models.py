import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class Chunk(BaseModel):
    """One retrievable unit of a source, with everything needed to cite and attribute it."""

    source_id: str
    native_id: str
    title: str
    url: str
    source_version: str
    language: str
    retrieved_at: str
    license: str
    attribution: str
    text: str
    heading_path: list[str] = []
    chunk_index: int = 0
    # Enclosing units, so "Article 50" finds every "AI Act Art. 50(n)".
    parent_ids: list[str] = []
    # Same value for the EN and DE text of one legal unit.
    unit_key: str = ""
    aliases: list[str] = []
    meta: dict[str, Any] = {}

    @property
    def point_id(self) -> str:
        key = f"{self.source_id}|{self.native_id}|{self.language}|{self.chunk_index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    def embedding_text(self) -> str:
        return "\n".join([self.native_id, self.title, *self.heading_path, self.text])


class Edge(BaseModel):
    src_id: str
    rel: str
    dst_id: str
    origin: str


@dataclass
class Snapshot:
    """The raw files of one source version, as fetched."""

    source_id: str
    version: str
    retrieved_at: str
    files: dict[str, bytes]
    urls: dict[str, str] = field(default_factory=dict)


def split_text(text: str, max_chars: int) -> list[str]:
    """Split one unit's text at paragraph, then line boundaries, so no part exceeds max_chars."""
    if len(text) <= max_chars:
        return [text]
    for separator in ("\n\n", "\n", ". "):
        pieces = text.split(separator)
        if len(pieces) > 1:
            break
    else:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
    parts: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}{separator}{piece}" if current else piece
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = piece
    parts.append(current)
    return [p for part in parts for p in split_text(part, max_chars)]


def finalize(chunks: list[Chunk], max_chars: int) -> list[Chunk]:
    """Split oversized chunks; the parts keep their native ID and are numbered per unit."""
    out: list[Chunk] = []
    counters: dict[tuple[str, str], int] = {}
    for chunk in chunks:
        for part in split_text(chunk.text, max_chars):
            key = (chunk.native_id, chunk.language)
            index = counters.get(key, 0)
            counters[key] = index + 1
            out.append(chunk.model_copy(update={"text": part, "chunk_index": index}))
    return out


def first_sentence(text: str, max_chars: int = 160) -> str:
    """The text up to its first sentence end, cut at a word boundary beyond max_chars."""
    # shortcut: "e.g. " ends a sentence too; use a sentence splitter if summaries read badly.
    sentence = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    return sentence if len(sentence) <= max_chars else sentence[:max_chars].rsplit(" ", 1)[0] + "…"


def overview_chunk(
    entries: list[Chunk], *, native_id: str, title: str, url: str, intro: str
) -> Chunk:
    """One chunk naming a list (an OWASP top 10, the ATLAS tactics) and all its entries in ID
    order, so list questions find the list by its name and get every entry at once."""
    if not entries:
        raise ValueError(f"{native_id}: no entries to list (did the source's format change?)")
    first: dict[str, Chunk] = {}
    for entry in entries:
        first.setdefault(entry.native_id, entry)
    lines = [f"{i} {c.title}: {first_sentence(c.text)}" for i, c in sorted(first.items())]
    source = entries[0]
    return Chunk(
        source_id=source.source_id,
        native_id=native_id,
        title=title,
        url=url,
        source_version=source.source_version,
        language=source.language,
        retrieved_at=source.retrieved_at,
        license=source.license,
        attribution=source.attribution,
        text="\n".join([intro, *lines]),
        heading_path=["Overview"],
        meta={"kind": "overview"},
    )


def clean(text: str) -> str:
    """Collapse runs of spaces and blank lines that PDF and HTML extraction leave behind."""
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
