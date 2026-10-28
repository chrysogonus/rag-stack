import hashlib
import importlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from rag_stack.config import Settings
from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, finalize
from rag_stack.ingestion.registry import SOURCES

logger = logging.getLogger(__name__)

MODULES = {
    "atlas": "atlas",
    "owasp-llm-2026": "owasp_llm",
    "owasp-agentic-2026": "owasp_agentic",
    "eu-ai-act": "eu_law",
    "ki-mig": "gesetze_im_internet",
    "vulns": "vulns",
    "attack": "attack",
    "capec": "capec",
    "cwe": "cwe",
    "d3fend": "d3fend",
}
CONFIG = Path(__file__).parents[3] / "config/sources.yaml"


def source_module(source_id: str):
    return importlib.import_module(f"rag_stack.ingestion.sources.{MODULES[source_id]}")


def parser_sha(module: ModuleType) -> str:
    """sha256 of a parser's code: its module, the other sources' modules it borrows from and the
    ID detection that finds its references."""
    borrowed = (f"{__package__}.sources.", "rag_stack.retrieval.ids")
    names = {module.__name__} | {
        f.__module__
        for f in vars(module).values()
        if callable(f) and getattr(f, "__module__", "").startswith(borrowed)
    }
    code = b"".join(Path(str(sys.modules[n].__file__)).read_bytes() for n in sorted(names))
    return hashlib.sha256(code).hexdigest()


def make_fetcher(settings: Settings) -> Fetcher:
    nvd_key = settings.nvd_api_key.get_secret_value()
    github_token = settings.github_token.get_secret_value()
    headers = {}
    if nvd_key:
        headers["services.nvd.nist.gov"] = {"apiKey": nvd_key}
    if github_token:
        headers["api.github.com"] = {"Authorization": f"Bearer {github_token}"}
    return Fetcher(
        settings.fetch_user_agent,
        Path(settings.data_dir) / "cache",
        settings.fetch_cache_ttl_hours,
        # NVD allows 5 requests per 30 s without a key and 50 with one; GitHub's API 60 an hour
        # without a token and 5,000 with one.
        host_intervals={
            "services.nvd.nist.gov": 0.7 if nvd_key else 6.5,
            "api.github.com": 1.0 if github_token else 61.0,
        },
        headers=headers,
    )


def digest(files: dict[str, bytes]) -> str:
    return hashlib.sha256(
        "".join(f"{n}:{hashlib.sha256(files[n]).hexdigest()}\n" for n in sorted(files)).encode()
    ).hexdigest()


def ingest(source_id: str, settings: Settings, fetcher: Fetcher) -> str:
    """Fetch, snapshot and parse one source. Returns a one-line status."""
    config: dict[str, Any] = {"id": source_id, **yaml.safe_load(CONFIG.read_text())[source_id]}
    module = source_module(source_id)
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
    snapshot: Snapshot = module.fetch(fetcher, config, retrieved_at)
    data = Path(settings.data_dir)
    raw = data / "raw" / source_id / safe(snapshot.version)
    processed = data / "processed" / source_id / safe(snapshot.version)
    sha = digest(snapshot.files)
    # Unchanged input and unchanged parser code: nothing to do. A parser fix re-parses.
    parser = parser_sha(module)
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
                "license": SOURCES[source_id].license,
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


def safe(version: str) -> str:
    return "".join(c if c.isalnum() or c in ".-_@" else "_" for c in version)


def write_processed(directory: Path, chunks: list[Chunk], edges: list[Edge], sha: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "chunks.jsonl").write_text("".join(c.model_dump_json() + "\n" for c in chunks))
    (directory / "edges.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in edges))
    (directory / "sha256").write_text(sha)


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
