import hashlib
import importlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from rag_stack.config import Settings
from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, finalize
from rag_stack.pack import Source, package

logger = logging.getLogger(__name__)


def source_module(source: Source) -> ModuleType:
    """The source's parser: a module with fetch() and parse()."""
    return importlib.import_module(source.parser)


def parser_sha(module: ModuleType, pack: str) -> str:
    """sha256 of a parser's code: its module and the modules of the pack (package prefix `pack`)
    it borrows functions from, such as another parser's helpers or the pack's ID detection."""
    names = {module.__name__} | {
        f.__module__
        for f in vars(module).values()
        if callable(f) and getattr(f, "__module__", "").startswith(pack)
    }
    code = b"".join(Path(str(sys.modules[n].__file__)).read_bytes() for n in sorted(names))
    return hashlib.sha256(code).hexdigest()


def make_fetcher(settings: Settings) -> Fetcher:
    """A fetcher with the pack's user agent and per-host pacing and credentials."""
    fetch = settings.pack.fetch
    intervals, headers = {}, {}
    for host, rules in fetch.hosts.items():
        intervals[host] = rules.interval
        if (credential := rules.credential) and (value := settings.secret(credential.env)):
            intervals[host] = credential.interval
            headers[host] = {credential.header: credential.value.format(value)}
    return Fetcher(
        fetch.user_agent,
        Path(settings.data_dir) / "cache",
        settings.fetch_cache_ttl_hours,
        host_intervals=intervals,
        headers=headers,
    )


def digest(files: dict[str, bytes]) -> str:
    return hashlib.sha256(
        "".join(f"{n}:{hashlib.sha256(files[n]).hexdigest()}\n" for n in sorted(files)).encode()
    ).hexdigest()


def ingest(source_id: str, settings: Settings, fetcher: Fetcher) -> str:
    """Fetch, snapshot and parse one source. Returns a one-line status."""
    source = settings.pack.sources[source_id]
    config: dict[str, Any] = {"id": source_id, **source.config}
    module = source_module(source)
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
    snapshot: Snapshot = module.fetch(fetcher, config, retrieved_at)
    data = Path(settings.data_dir)
    raw = data / "raw" / source_id / safe(snapshot.version)
    processed = data / "processed" / source_id / safe(snapshot.version)
    sha = digest(snapshot.files)
    # Unchanged input and unchanged parser code: nothing to do. A parser fix re-parses.
    parser = parser_sha(module, package(settings.pack.root) + ".")
    manifest = raw / "manifest.json"
    if manifest.exists() and json.loads(manifest.read_text())["sha256"] == sha:
        done = processed / "parser.sha256"
        if done.exists() and done.read_text() == parser:
            return f"{source_id} {snapshot.version}: unchanged (sha256 {sha[:12]}), skipped"

    raw.mkdir(parents=True, exist_ok=True)
    for name, content in snapshot.files.items():
        (raw / name).write_bytes(content)
    (raw / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(c).hexdigest()}  {n}\n" for n, c in sorted(snapshot.files.items())
        )
    )
    manifest.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "version": snapshot.version,
                "retrieved_at": snapshot.retrieved_at,
                "sha256": sha,
                "urls": snapshot.urls,
                "license": source.license,
            },
            indent=2,
        )
    )
    chunks, edges = module.parse(snapshot)
    chunks = finalize(chunks, settings.max_chunk_chars)
    # The indexer re-embeds a source when this changes: new input or new parser.
    write_processed(processed, chunks, edges, hashlib.sha256(f"{sha}{parser}".encode()).hexdigest())
    (processed / "parser.sha256").write_text(parser)
    (data / "processed" / source_id / "LATEST").write_text(safe(snapshot.version))
    return f"{source_id} {snapshot.version}: {len(chunks)} chunks, {len(edges)} edges"


def reparse(source_id: str, settings: Settings) -> tuple[str, list[Chunk], list[Edge]]:
    """Parse the latest raw snapshot of a source again, without network and without writing:
    (version, chunks, edges). Shows whether a code change alters what a source turns into."""
    data = Path(settings.data_dir)
    raw = data / "raw" / source_id / (data / "processed" / source_id / "LATEST").read_text().strip()
    manifest = json.loads((raw / "manifest.json").read_text())
    names = [line.split("  ", 1)[1] for line in (raw / "SHA256SUMS").read_text().splitlines()]
    # Parsers see files in fetch order, which the manifest's urls keep; SHA256SUMS is sorted.
    names = [n for n in manifest["urls"] if n in names] + [
        n for n in names if n not in manifest["urls"]
    ]
    snapshot = Snapshot(
        source_id=source_id,
        version=manifest["version"],
        retrieved_at=manifest["retrieved_at"],
        files={name: (raw / name).read_bytes() for name in names},
        urls=manifest["urls"],
    )
    chunks, edges = source_module(settings.pack.sources[source_id]).parse(snapshot)
    return snapshot.version, finalize(chunks, settings.max_chunk_chars), edges


def safe(version: str) -> str:
    return "".join(c if c.isalnum() or c in ".-_@" else "_" for c in version)


def write_processed(directory: Path, chunks: list[Chunk], edges: list[Edge], sha: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "chunks.jsonl").write_text(jsonl(chunks))
    (directory / "edges.jsonl").write_text(jsonl(edges))
    (directory / "sha256").write_text(sha)


def jsonl(items: list[Chunk] | list[Edge]) -> str:
    return "".join(item.model_dump_json() + "\n" for item in items)


def load_processed(
    settings: Settings, source_id: str
) -> tuple[str, list[Chunk], list[Edge]] | None:
    """The latest processed snapshot of a source: (sha256, chunks, edges)."""
    root = Path(settings.data_dir) / "processed" / source_id
    if not (root / "LATEST").exists():
        return None
    directory = root / (root / "LATEST").read_text().strip()
    chunks = [Chunk.model_validate_json(line) for line in (directory / "chunks.jsonl").open()]
    edges = [Edge.model_validate_json(line) for line in (directory / "edges.jsonl").open()]
    return (directory / "sha256").read_text().strip(), chunks, edges
