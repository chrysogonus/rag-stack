"""A folder of documents in the pack (`parser: files`): Markdown, text, HTML, PDF and Word.

config:
  path: docs                 # the folder, relative to the pack (default docs)
  include: ["**/*.md"]       # globs within it (default: every document)
  url_template: https://example.org/{path}   # a document's link (default: the source's url)
  language: en               # (default en)
  version: "2026.1"          # (default: the content's digest)"""

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docx import Document
from docx.table import Table
from pypdf import PdfReader

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.generic.chunking import (
    Block,
    document_chunks,
    html_blocks,
    markdown_blocks,
    snapshot,
    stem,
    unstamped,
)
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean


def text(content: bytes) -> str:
    return content.decode("utf-8-sig", errors="replace")


def pdf_blocks(content: bytes) -> list[Block]:
    # shortcut: one section per page, whatever the outline says; split by the outline's
    # bookmarks if answers need sections that span pages.
    pages = [clean(page.extract_text()) for page in PdfReader(io.BytesIO(content)).pages]
    return [b for n, page in enumerate(pages, start=1) for b in [(1, f"Page {n}"), (0, page)]]


def docx_blocks(content: bytes) -> list[Block]:
    """Title and Heading 1-3 paragraphs head sections; tables become rows of cells."""
    blocks: list[Block] = []
    for item in Document(io.BytesIO(content)).iter_inner_content():
        if isinstance(item, Table):
            rows = [" | ".join(c.text.strip() for c in row.cells) for row in item.rows]
            blocks.append((0, "\n".join(rows)))
            continue
        style = getattr(item.style, "name", None) or ""
        level = 1 if style == "Title" else int(style[-1]) if style[:-1] == "Heading " else 0
        if item.text.strip():
            blocks.append((level if level <= 3 else 0, item.text.strip()))
    return blocks


FORMATS: dict[str, Callable[[bytes], list[Block]]] = {
    ".md": lambda content: markdown_blocks(text(content)),
    ".markdown": lambda content: markdown_blocks(text(content)),
    ".txt": lambda content: [(0, text(content))],
    ".html": html_blocks,
    ".htm": html_blocks,
    ".pdf": pdf_blocks,
    ".docx": docx_blocks,
}


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    folder = Path(config["pack_root"]) / config.get("path", "docs")
    found = {
        path
        for pattern in config.get("include", ["**/*"])
        for path in folder.glob(pattern)
        if path.is_file() and path.suffix.lower() in FORMATS
    }
    if not found:
        raise ValueError(f"{config['id']}: no documents in {folder}")
    names = sorted(p.relative_to(folder).as_posix() for p in found)
    template = config.get("url_template")
    urls = {n: template.format(path=n) if template else config["source_url"] for n in names}
    return snapshot(config, retrieved_at, {n: (folder / n).read_bytes() for n in names}, urls)


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    _, files, common = unstamped(snapshot)
    chunks = []
    for name, content in files.items():
        blocks = FORMATS[Path(name).suffix.lower()](content)
        url = snapshot.urls[name]
        chunks += document_chunks(name, blocks, title=stem(name), url=url, **common)
    return chunks, []
