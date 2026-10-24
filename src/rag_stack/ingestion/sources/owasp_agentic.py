import io
import logging
import re
from typing import Any

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["owasp-agentic-2026"]
SECTIONS = (
    "Description",
    "Common Examples of the Vulnerability",
    "Example Attack Scenarios",
    "Prevention and Mitigation Guidelines",
    "References",
)
PAGE_NOISE = re.compile(r"^(=====PAGE \d+=====|Page \d+|genai\.owasp\.org)$")


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    pdf = fetcher.get(config["pdf_url"])
    if not pdf.startswith(b"%PDF"):
        raise ValueError(f"{config['pdf_url']} did not return a PDF")
    return Snapshot(
        INFO.id,
        config["version"],
        retrieved_at,
        {"agentic-top10.pdf": pdf},
        {"agentic-top10.pdf": config["page_url"]},
    )


def pdf_text(pdf: bytes) -> str:
    from pypdf import PdfReader

    # pypdf logs a warning per font it can't fully decode; the text is still fine.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    pages = PdfReader(io.BytesIO(pdf)).pages
    return "\n".join(f"=====PAGE {i + 1}=====\n{p.extract_text()}" for i, p in enumerate(pages))


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    return parse_text(pdf_text(snapshot.files["agentic-top10.pdf"]), snapshot), []


def parse_text(text: str, snapshot: Snapshot) -> list[Chunk]:
    """Split the extracted text into ASIxx entries, then each entry into its sections."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if not PAGE_NOISE.match(line)]
    # An entry starts at an "ASIxx: Title" line whose next "Description" heading follows
    # within three lines (the table of contents has page numbers after its headings).
    starts = []
    for i, line in enumerate(lines):
        if re.match(r"ASI\d{2}: ", line) and "Description" in lines[i + 1 : i + 4]:
            starts.append(i)
    end = next(
        (
            i
            for i, line in enumerate(lines)
            if starts and i > starts[-1] and line.startswith("Appendix A")
        ),
        len(lines),
    )
    chunks = []
    for start, stop in zip(starts, [*starts[1:], end], strict=True):
        description_at = lines.index("Description", start)
        heading = " ".join(line for line in lines[start:description_at] if line)
        native_id, _, title = heading.partition(": ")
        section, body = None, []
        for line in [*lines[description_at:stop], "References"]:
            if line in SECTIONS:
                if section and section != "References" and body:
                    chunks.append(entry_chunk(native_id, title.strip(), section, body, snapshot))
                section, body = line, []
            else:
                body.append(line)
    return chunks


def entry_chunk(native_id: str, title: str, section: str, body: list[str], snapshot: Snapshot):
    return Chunk(
        source_id=INFO.id,
        native_id=native_id,
        title=title,
        url=snapshot.urls["agentic-top10.pdf"],
        source_version=snapshot.version,
        language="en",
        retrieved_at=snapshot.retrieved_at,
        license=INFO.license,
        attribution=INFO.attribution,
        text=clean(unwrap("\n".join(body))),
        heading_path=[f"{native_id} {title}", section],
    )


def unwrap(text: str) -> str:
    """Rejoin PDF lines that wrap mid-sentence; keep a break before numbered items."""
    return re.sub(r"(?<=[^\n])\n(?!\d+\. |\n)", " ", text).replace("- \n", "-")
