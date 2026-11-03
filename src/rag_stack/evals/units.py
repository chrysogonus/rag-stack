"""Retrieval checks generated from the corpus itself, with no golden set and no LLM calls.

For a sample of units of every source: asking for a unit's ID ranks it first, searching for its
title (without the ID) finds it in the top 10, and asking what a unit relates to finds the units
its edges point to."""

import asyncio
import random
from collections import Counter
from statistics import mean

from rag_stack.config import Settings
from rag_stack.ingestion.models import Chunk
from rag_stack.ingestion.pipeline import load_processed
from rag_stack.retrieval.retriever import KnowledgeBase, open_knowledge_base

# shortcut: a unit with more neighbors than fit next to it in the top 10 may rank a correct one
# out, so only units with this few are checked; raise it with the retrieval limit.
MAX_DEGREE = 5


def main_language(units: list[Chunk]) -> str:
    """The language a source's units are asked about in: English, or the source's own language
    when it has no English units (a German law)."""
    return "en" if any(c.language == "en" for c in units) else units[0].language if units else "en"


async def ranked(kb: KnowledgeBase, query: str) -> list[str]:
    return [r.chunk.native_id for r in await kb.retrieve(query)]


async def main(settings: Settings, per_source: int = 50, kb: KnowledgeBase | None = None) -> int:
    kb = kb or await asyncio.to_thread(open_knowledge_base, settings)
    rng = random.Random(0)  # noqa: S311 (sampling): the same units every run
    rows: list[tuple[str, str, str, bool]] = []
    sources = settings.pack.sources
    corpus = {s: p for s in sources if (p := load_processed(settings, s))}
    indexed = {c.native_id for _, chunks, _ in corpus.values() for c in chunks}
    for source, (_, chunks, edges) in corpus.items():
        first = [c for c in chunks if c.chunk_index == 0 and c.meta.get("kind") != "overview"]
        units = [c for c in first if c.language == main_language(first)]
        titles = Counter(c.title for c in units)
        for unit in rng.sample(units, min(per_source, len(units))):
            found = await ranked(kb, f"What is {unit.native_id}?")
            rows.append((source, "id", unit.native_id, found[:1] == [unit.native_id]))
            # A title shared by several units (an article's paragraphs) or naming an ID isn't a
            # search for this one unit.
            if titles[unit.title] == 1 and not settings.pack.detect_ids(unit.title):
                found = await ranked(kb, unit.title)
                rows.append((source, "title", unit.native_id, unit.native_id in found[:10]))
        linked = [
            e
            for e in edges
            if e.src_id in indexed
            and e.dst_id in indexed
            and len(kb.graph.neighbors(e.src_id)) <= MAX_DEGREE
        ]
        for edge in rng.sample(linked, min(per_source, len(linked))):
            found = await ranked(kb, f"Which units are related to {edge.src_id}?")
            rows.append((source, "related", f"{edge.src_id} → {edge.dst_id}", edge.dst_id in found))

    failed = 0
    for check in ("id", "title", "related"):
        print(f"{check}:")
        for source in sources:
            group = [ok for s, c, _, ok in rows if s == source and c == check]
            if group:
                print(f"  {source:20} {sum(group):4} / {len(group):<4} {mean(group):.3f}")
    for source, check, unit, ok in rows:
        if not ok:
            failed += check == "id"
            print(f"miss {check:8} {source:20} {unit}")
    # An ID that doesn't rank its own unit first is a bug; title and related misses are scores.
    return 1 if failed else 0
