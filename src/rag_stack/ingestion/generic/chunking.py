"""Sections of a document, and the snapshot plumbing the generic sources share.

A document becomes blocks: (1-3, heading) or (0, text). Each heading starts a unit whose ID is
the document's path and the heading's anchor, `guides/travel.md#hotels`, inside the document
(`parent_ids`), so asking for the document finds every section of it."""

import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

from bs4 import BeautifulSoup

from rag_stack.ingestion.models import Chunk, Snapshot, clean
from rag_stack.ingestion.pipeline import digest

Block = tuple[int, str]
CONFIG = "_config.json"
# Settings of this checkout, not of the source: they must not change its digest.
LOCAL = {"pack_root"}

HEADING = re.compile(r"^(#{1,3})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
FENCE = re.compile(r"^[ \t]*(```|~~~)")
# Not text of the page: what a browser runs or shows around every page.
CHROME = ["script", "style", "noscript", "template", "nav", "footer", "aside", "form"]
BLOCKS = ["p", "li", "div", "br", "tr", "pre", "blockquote", "dt", "dd", "h4", "h5", "h6"]


def markdown_blocks(text: str) -> list[Block]:
    """ATX headings of the first three levels outside code fences; the rest is text."""
    blocks: list[Block] = []
    body: list[str] = []
    fenced = False

    def flush() -> None:
        if text := "\n".join(body).strip():
            blocks.append((0, text))
        body.clear()

    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        if not fenced and (heading := HEADING.match(line)):
            flush()
            blocks.append((len(heading[1]), heading[2]))
        else:
            body.append(line)
    flush()
    return blocks


def html_blocks(html: bytes | str) -> list[Block]:
    """The page's main text, split at its h1-h3 headings."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(CHROME):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    for tag in root.find_all(BLOCKS):
        tag.insert_after("\n\n")
    for heading in root.find_all(["h1", "h2", "h3"]):
        text = " ".join(heading.get_text(" ").split())
        heading.replace_with(f"\n\x00{heading.name[1]}{text}\n")
    parts = re.split(r"\n\x00(\d)(.*)\n", root.get_text())
    blocks: list[Block] = [(0, parts[0])]
    for i in range(1, len(parts), 3):
        blocks += [(int(parts[i]), parts[i + 1]), (0, parts[i + 2])]
    return [(level, clean(text)) for level, text in blocks if level or clean(text)]


def html_title(html: bytes | str) -> str:
    title = BeautifulSoup(html, "lxml").title
    return title.get_text(" ", strip=True) if title else ""


def anchor(heading: str) -> str:
    """GitHub's anchor for a heading: lowercase, punctuation dropped, spaces as hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).strip().replace(" ", "-")


def document_chunks(
    path: str, blocks: Iterable[Block], *, title: str, **common: Any
) -> list[Chunk]:
    """One unit per section; text before the first heading is the document's own unit, titled
    `title`. `common` holds the Chunk fields every unit of the document shares."""
    sections: list[tuple[list[str], list[str]]] = [([], [])]
    headings: list[str] = []
    for level, text in blocks:
        if level:
            headings = [*headings[: level - 1], text]
            sections.append((headings, []))
        else:
            sections[-1][1].append(text)
    taken: set[str] = set()
    suffixes: Counter[str] = Counter()
    chunks = []
    for heads, body in sections:
        if not (text := "\n\n".join(body).strip()):
            continue
        native_id = path
        if heads:
            # A repeated heading gets -1, -2, ... skipping anchors a heading already has.
            name = base = anchor(heads[-1])
            while name in taken:
                suffixes[base] += 1
                name = f"{base}-{suffixes[base]}"
            taken.add(name)
            native_id = f"{path}#{name}"
        chunks.append(
            Chunk(
                native_id=native_id,
                title=heads[-1] if heads else title,
                heading_path=heads,
                parent_ids=[path] if heads else [],
                text=text,
                **common,
            )
        )
    return chunks


def stem(path: str) -> str:
    return PurePosixPath(path).stem


def snapshot(
    config: dict[str, Any], retrieved_at: str, files: dict[str, bytes], urls: dict[str, str]
) -> Snapshot:
    """The fetched files plus the source's config, so parse() sees the license, fields and
    templates it was fetched with and a config change counts as new input. The version is the
    config's, or the content's digest."""
    stamped = {k: v for k, v in config.items() if k not in LOCAL}
    files = {**files, CONFIG: json.dumps(stamped, sort_keys=True, ensure_ascii=False).encode()}
    version = str(config.get("version") or digest(files)[:12])
    return Snapshot(config["id"], version, retrieved_at, files, urls)


def unstamped(snapshot: Snapshot) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Any]]:
    """(config, the fetched files, the Chunk fields every unit of the snapshot shares)."""
    config = json.loads(snapshot.files[CONFIG])
    common = {
        "source_id": snapshot.source_id,
        "source_version": snapshot.version,
        "retrieved_at": snapshot.retrieved_at,
        "license": config["license"],
        "attribution": config["attribution"],
        "language": config.get("language", "en"),
    }
    return config, {n: b for n, b in snapshot.files.items() if n != CONFIG}, common
