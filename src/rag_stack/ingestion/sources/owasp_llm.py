import re
from typing import Any

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean, overview_chunk
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["owasp-llm-2026"]
APPENDIX = "Appendix_A_Related_Framework_Mappings.md"
TARGET_ID = re.compile(
    r"\b(ASI\d{2}|AML\.T[A]?\d{4}(?:\.\d{3})?|AML\.M\d{4}|CWE-\d+|TA\d{4}|T\d{4})\b"
)


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    base = f"https://raw.githubusercontent.com/{config['repo']}/{config['ref']}/{config['path']}"
    files = {name: fetcher.get(f"{base}/{name}") for name in config["files"]}
    blob = f"https://github.com/{config['repo']}/blob/{config['ref']}/{config['path']}"
    return Snapshot(
        INFO.id,
        f"2026@{config['ref'][:7]}",
        retrieved_at,
        files,
        {name: f"{blob}/{name}" for name in files},
    )


def slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    chunks: list[Chunk] = []
    for name, raw in snapshot.files.items():
        if name == APPENDIX:
            continue
        text = raw.decode()
        title_match = re.match(r"##\s+(LLM\d{2}:2026)\s+(.+)", text)
        if not title_match:
            raise ValueError(f"{name}: no '## LLMxx:2026 <title>' heading")
        native_id, title = title_match.groups()
        # One chunk per "###" section; "####" sub-headings stay inside their section.
        for section in re.split(r"^(?=### )", text, flags=re.MULTILINE)[1:]:
            heading, _, body = section.partition("\n")
            heading = heading.removeprefix("### ").strip()
            chunks.append(
                Chunk(
                    source_id=INFO.id,
                    native_id=native_id,
                    title=title.strip(),
                    url=f"{snapshot.urls[name]}#{slug(heading)}",
                    source_version=snapshot.version,
                    language="en",
                    retrieved_at=snapshot.retrieved_at,
                    license=INFO.license,
                    attribution=INFO.attribution,
                    text=clean(body),
                    heading_path=[f"{native_id} {title.strip()}", heading],
                )
            )
    overview = overview_chunk(
        [c for c in chunks if c.heading_path[1] == "Description"],
        native_id="OWASP LLM Top 10 2026",
        title=f"{INFO.name}: overview",
        url=next(iter(snapshot.urls.values())).rsplit("/", 1)[0],
        intro=f"The {INFO.name} lists these risks, by number:",
    )
    edges = parse_mappings(snapshot.files[APPENDIX].decode()) if APPENDIX in snapshot.files else []
    return [*chunks, overview], edges


def parse_mappings(appendix: str) -> list[Edge]:
    """Appendix A tables: '| **LLM01** Title | ● ASI01 — Title | why |'; blank first cells
    continue the previous risk. ● marks a primary mapping, ○ a supporting one."""
    edges: list[Edge] = []
    risk = None
    for line in appendix.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not line.startswith("|"):
            continue
        if found := re.search(r"\*\*LLM(\d{2})\*\*", cells[0]):
            risk = f"LLM{found.group(1)}:2026"
        elif cells[0]:
            risk = None
        target = TARGET_ID.search(cells[1])
        if risk and target:
            rel = "maps_to" if "●" in cells[1] else "maps_to_supporting"
            edges.append(Edge(src_id=risk, rel=rel, dst_id=target.group(1), origin=INFO.id))
    return edges
