"""Scheduled refresh: compare the ingested sources with what is served, check them, build a
candidate index generation, score its retrieval against the served one, and promote it only
if every check passes. Each run appends one line to data/refresh.log."""

import fcntl
import hashlib
import logging
from collections import defaultdict
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import yaml
from qdrant_client import QdrantClient, models

from rag_stack.config import Settings
from rag_stack.db import edges as edge_store
from rag_stack.db.edges import EdgeGraph
from rag_stack.evals import harness
from rag_stack.ingestion.models import Chunk, Edge
from rag_stack.ingestion.pipeline import MODULES, load_processed
from rag_stack.llm.embeddings import Embedder, Reranker, SparseEmbedder
from rag_stack.retrieval import generations as gens
from rag_stack.retrieval.index import embedding_in, ensure_collection, index_source, match
from rag_stack.retrieval.retriever import knowledge_base

logger = logging.getLogger(__name__)

MAX_DROP = 0.10  # a source losing more of its chunks or IDs than this blocks the refresh
MAX_REGRESSION = 0.02  # how far recall@k or MRR may fall below the served generation
METRICS = ("recall_at_10", "mrr")

Models = Callable[[], tuple[Embedder, SparseEmbedder, Reranker]]
Processed = dict[str, tuple[str, list[Chunk], list[Edge]]]


@dataclass(frozen=True)
class Diff:
    added: int
    removed: int
    changed: int
    chunks: tuple[int, int]
    ids: tuple[int, int]


def unit_hashes(chunks: Iterable[Chunk]) -> dict[str, str]:
    """One hash per native ID over all its chunks (parts and languages)."""
    parts: dict[str, list[str]] = defaultdict(list)
    for c in chunks:
        parts[c.native_id].append(f"{c.language}|{c.chunk_index}|{c.embedding_text()}")
    return {
        native_id: hashlib.sha256("\0".join(sorted(texts)).encode()).hexdigest()
        for native_id, texts in parts.items()
    }


def diff(before: list[Chunk], after: list[Chunk]) -> Diff:
    old, new = unit_hashes(before), unit_hashes(after)
    return Diff(
        added=len(new.keys() - old.keys()),
        removed=len(old.keys() - new.keys()),
        changed=sum(old[i] != new[i] for i in old.keys() & new.keys()),
        chunks=(len(before), len(after)),
        ids=(len(old), len(new)),
    )


def gate(diffs: dict[str, Diff], max_drop: float = MAX_DROP) -> list[str]:
    """Why the candidate must not be built: a source that shrank too much."""
    reasons = []
    for source_id, d in diffs.items():
        for what, (old, new) in (("chunks", d.chunks), ("IDs", d.ids)):
            if old and new < old * (1 - max_drop):
                reasons.append(f"{source_id} {what} {old}→{new} ({(new - old) / old:+.0%})")
    return reasons


def missing_gold(chunks: Iterable[Chunk]) -> list[str]:
    found = {c.native_id for c in chunks}
    return sorted({g for case in harness.load_cases() for g in case["gold_ids"]} - found)


def served_chunks(client: QdrantClient, collection: str) -> dict[str, tuple[str, list[Chunk]]]:
    """What a collection holds, per source: (processed sha256, chunks)."""
    found: dict[str, tuple[str, list[Chunk]]] = {}
    offset = None
    while True:
        records, offset = client.scroll(collection, limit=512, offset=offset, with_payload=True)
        for r in records:
            payload = r.payload or {}
            found.setdefault(payload["source_id"], (payload["processed_sha"], []))[1].append(
                Chunk.model_validate(payload)
            )
        if offset is None:
            return found


def adopt_legacy(client: QdrantClient, alias: str, database_url: str) -> str | None:
    """Turn the collection indexed before generations into the first generation behind the
    alias. Idempotent. Never serves a generation it finds: an unserved one may have been blocked
    or left half built, so without alias or collection the refresh builds and checks a new one."""
    if alias in gens.aliases(client):
        return None
    if gens.serving(client, alias) == alias:
        generation = gens.new_generation()
        target = gens.collection_name(alias, generation)
        vectors = cast(
            dict[str, models.VectorParams], client.get_collection(alias).config.params.vectors
        )
        ensure_collection(client, target, vectors["dense"].size)
        gens.copy_points(client, alias, target)
        if client.count(target, exact=True).count != client.count(alias, exact=True).count:
            client.delete_collection(target)
            raise RuntimeError(f"copying {alias} into {target} lost points; {alias} is untouched")
        edge_store.copy_edges(database_url, "", generation)
        client.delete_collection(alias)
        gens.promote(client, alias, target)
        edge_store.delete_edge_generations(database_url, [generation])
        return f"adopted {alias} as {target}"
    return None


def build_candidate(
    client: QdrantClient,
    served: str | None,
    served_shas: dict[str, str],
    candidate: str,
    processed: Processed,
    embedder: Embedder,
    sparse: SparseEmbedder,
) -> int:
    """Fill the candidate: unchanged sources are copied from the served collection with their
    vectors; of a changed source only new and changed chunks are embedded. Returns the number of
    points it should hold."""
    for source_id, (sha, chunks, _) in processed.items():
        if served and served_shas.get(source_id) == sha:
            only = models.Filter(must=[match("source_id", source_id)])
            gens.copy_points(client, served, candidate, only)
        else:
            index_source(
                client, candidate, source_id, sha, chunks, embedder, sparse, reuse_from=served
            )
    return sum(len(chunks) for _, chunks, _ in processed.values())


def tidy(client: QdrantClient, alias: str, database_url: str, *keep: str | None) -> None:
    """Delete every generation except the served, the previous and the given ones."""
    kept = {c for c in (gens.serving(client, alias), gens.previous(client, alias), *keep) if c}
    gens.prune(client, alias, kept)
    edge_store.delete_edge_generations(database_url, [gens.generation_of(alias, c) for c in kept])


async def refresh(
    settings: Settings,
    client: QdrantClient,
    failed: list[str],
    load_models: Models,
    force: bool = False,
    load_embedder: Callable[[str], Embedder] | None = None,
) -> tuple[int, str]:
    """One refresh after ingesting; `failed` are sources whose ingest failed (their previous
    snapshot is used). `force` skips the shrink check. A new embedding model rebuilds every
    source; `load_embedder` then loads the served one by name, to score the served generation as
    it runs. Returns (exit code, log line)."""
    alias, db = settings.qdrant_collection, settings.database_url
    notes = [f"ingest failed: {', '.join(failed)} (previous snapshot kept)"] if failed else []
    generation = "-"
    try:
        if adopted := adopt_legacy(client, alias, db):
            notes.append(adopted)
        served = gens.serving(client, alias)
        before = served_chunks(client, served) if served else {}
        served_shas = {s: sha for s, (sha, _) in before.items()}
        processed: Processed = {s: p for s in MODULES if (p := load_processed(settings, s))}
        shas = {s: sha for s, (sha, _, _) in processed.items()}
        served_model = embedding_in(client, served) if served else None
        switch = served_model not in (None, settings.embedding)
        if shas == served_shas and not switch:
            tidy(client, alias, db)
            return log(settings, 0, generation, "NO CHANGE", notes)

        diffs = {
            s: diff(before.get(s, ("", []))[1], chunks)
            for s, (sha, chunks, _) in processed.items()
            if served_shas.get(s) != sha
        }
        notes.insert(0, changes(diffs, processed, len(processed) - len(diffs)))
        if switch:
            notes.insert(1, f"embedding {served_model} → {settings.embedding}: rebuilt in full")
        # A served source no longer in MODULES was retired on purpose: the candidate drops it.
        if removed := sorted(served_shas.keys() - MODULES.keys()):
            notes.insert(1, f"removed: {', '.join(removed)}")
        missing = served_shas.keys() - shas.keys() - set(removed)
        reasons = [f"{s} has no processed snapshot" for s in sorted(missing)]
        reasons += [] if force else gate(diffs)
        if missing := missing_gold(c for _, chunks, _ in processed.values() for c in chunks):
            reasons.append(f"gold IDs missing: {', '.join(missing)}")
        if reasons:
            tidy(client, alias, db)
            return log(settings, 1, generation, f"BLOCKED: {'; '.join(reasons)}", notes)

        embedder, sparse, reranker = load_models()
        generation = gens.new_generation()
        candidate = gens.collection_name(alias, generation)
        if client.collection_exists(candidate):  # never build into a collection in use
            raise RuntimeError(f"{candidate} exists already")
        ensure_collection(client, candidate, embedder.dim)
        # Vectors of another model are never copied or reused.
        expected = build_candidate(
            client, None if switch else served, served_shas, candidate, processed, embedder, sparse
        )
        for source_id, (_, _, edges) in processed.items():
            edge_store.replace_edges(db, generation, source_id, edges)
        if (points := client.count(candidate, exact=True).count) != expected:
            tidy(client, alias, db, candidate)
            return log(
                settings, 1, generation, f"BLOCKED: {points} points, {expected} expected", notes
            )

        async def scores(collection: str, queries: Embedder) -> dict[str, float | None]:
            graph = EdgeGraph(edge_store.load_edges(db, gens.generation_of(alias, collection)))
            kb = knowledge_base(settings, client, collection, queries, sparse, reranker, graph)
            return (await harness.retrieval_scores(kb, "all"))[0]["all"]

        new = await scores(candidate, embedder)
        old = None
        if served and served_model and switch:
            try:
                if load_embedder is None:
                    raise ValueError("no loader given")
                old = await scores(served, load_embedder(served_model))
            except Exception as error:
                notes.append(f"served generation not scored ({served_model}: {error})")
        elif served:
            old = await scores(served, embedder)
        notes.append(
            ", ".join(
                f"{m} {new[m]:.3f}" + (f" (served {old[m]:.3f})" if old else "") for m in METRICS
            )
        )
        thresholds = yaml.safe_load((harness.DATASET / "thresholds.yaml").read_text())
        reasons = [
            f"{m} {new[m]} < {thresholds[m]}" for m in METRICS if (new[m] or 0) < thresholds[m]
        ]
        if old:
            reasons += [
                f"{m} {new[m]:.3f} < served {old[m]:.3f} - {MAX_REGRESSION}"
                for m in METRICS
                if (new[m] or 0) < (old[m] or 0) - MAX_REGRESSION
            ]
        if reasons:
            tidy(client, alias, db, candidate)
            return log(settings, 1, generation, f"BLOCKED: {'; '.join(reasons)}", notes)
        gens.promote(client, alias, candidate)
        try:  # promoted is promoted: a failed cleanup must not hide it (the API restarts on it)
            tidy(client, alias, db)
        except Exception as error:
            logger.exception("cleanup after the promotion failed")
            notes.append(f"cleanup failed: {error}")
        return log(settings, 0, generation, "PROMOTED", notes)
    except Exception as error:
        logger.exception("refresh failed")
        return log(settings, 1, generation, f"FAILED: {error}", notes)


def changes(diffs: dict[str, Diff], processed: Processed, unchanged: int) -> str:
    parts = []
    for source_id, d in diffs.items():
        chunks = processed[source_id][1]
        version = chunks[0].source_version if chunks else ""
        parts.append(
            f"{source_id} {version}: +{d.added} -{d.removed} ~{d.changed} IDs, "
            f"{d.chunks[0]}→{d.chunks[1]} chunks"
        )
    return "; ".join([*parts, f"{unchanged} sources unchanged"])


def rollback(settings: Settings, client: QdrantClient) -> tuple[int, str]:
    alias = settings.qdrant_collection
    try:
        now, before = gens.rollback(client, alias)
    except ValueError as error:
        return log(settings, 1, "-", f"ROLLBACK FAILED: {error}", [])
    return log(settings, 0, gens.generation_of(alias, now), f"ROLLBACK from {before}", [])


def log(
    settings: Settings, code: int, generation: str, outcome: str, notes: list[str]
) -> tuple[int, str]:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = " | ".join([f"{stamp} {generation} {outcome}", *notes])
    with (Path(settings.data_dir) / "refresh.log").open("a") as f:
        f.write(line + "\n")
    return code, line


@contextmanager
def locked(settings: Settings) -> Generator[None]:
    """One refresh or index at a time: raises BlockingIOError if another one is running."""
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    with (Path(settings.data_dir) / ".refresh.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
