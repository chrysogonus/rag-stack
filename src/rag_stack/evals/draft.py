"""Draft candidate golden-set questions from indexed units the golden set doesn't cover yet.

Drafts go to drafts.jsonl, never into golden.jsonl: a person reviews each one, fixes or drops
it, sets `needs_review: false` and moves it into golden.jsonl. They are `test` questions: no
setting has been tuned on these units."""

import asyncio
import json
import random
import re
from typing import Any

from rag_stack.config import Settings
from rag_stack.evals.harness import DATASET, complete, judge_model, load_cases
from rag_stack.ingestion.models import Chunk, Edge
from rag_stack.ingestion.pipeline import MODULES, load_processed
from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS
from rag_stack.llm.base import ChatModel
from rag_stack.retrieval.ids import detect_ids

DRAFTS = DATASET / "drafts.jsonl"
LEGAL = {*EU_ACTS, *GERMAN_LAWS}
# What each category asks for; the drafter sees this and the unit's text.
KINDS = {
    "id-exact": "names the unit's id and asks what it is or says",
    "freshness": "asks about the unit's content in a user's own words, without naming its id",
    "german-legal": "is in German and asks for the exact wording of the provision, naming it",
    "cve": "asks about the vulnerability by its CVE id: affected package, impact or fixed version",
    "cross-source": "asks how the two units relate, naming one of them, so answering needs both",
}

PROMPT = """\
You write one evaluation question for a chatbot that answers only from a knowledge base on \
attacks on AI systems and EU AI regulation. The question must be answerable from the source \
text below alone, and the way a real user would ask it. It {kind}. Write it in {language}.

Also list two or three key facts: short statements, taken from the source text, that a correct \
answer must contain. Don't invent anything the text doesn't say.

Reply with JSON only: {{"question": "...", "key_facts": ["...", "..."]}}"""


def used_ids() -> set[str]:
    """Units already asked about, in golden.jsonl or an earlier draft: gold IDs and every ID a
    question, its previous question or its key facts name (a list question names its entries)."""
    cases = load_cases()
    if DRAFTS.exists():
        cases += [json.loads(line) for line in DRAFTS.read_text().splitlines() if line]
    named = (
        detect_ids(" ".join([c["question"], c.get("follow_up_of", ""), *c["key_facts"]]))
        for c in cases
    )
    return {g for case in cases for g in case["gold_ids"]} | {i for ids in named for i in ids}


def covered(chunk: Chunk, used: set[str]) -> bool:
    """Asked about by ID, by alias, or through an enclosing unit ("Article 5" covers 5(1))."""
    return bool({chunk.native_id, *chunk.aliases, *chunk.parent_ids} & used)


def candidates(settings: Settings, source: str, category: str) -> list[tuple[list[Chunk], str]]:
    """Unasked units of the source that fit the category, each with a note for the drafter: one
    unit, or the two ends of an edge between sources with the relation (it's in neither text)."""
    if (category == "german-legal" and source not in LEGAL) or (
        category == "cve" and source != "ai-vulns"
    ):
        raise ValueError(f"{category} questions don't fit {source}")
    corpus: dict[str, list[Chunk]] = {}
    edges: list[Edge] = []
    for source_id in MODULES:
        if processed := load_processed(settings, source_id):
            corpus[source_id] = [c for c in processed[1] if c.chunk_index == 0]
            if source_id == source:
                edges = processed[2]
    if source not in corpus:
        raise ValueError(f"{source}: not ingested, run `make ingest SOURCE={source}` first")
    used = used_ids()
    if category == "cross-source":
        first = {c.native_id: c for chunks in corpus.values() for c in chunks if c.language == "en"}
        pairs = {
            (e.src_id, e.dst_id): f"Relationship: {e.src_id} {e.rel} {e.dst_id}"
            for e in edges
            if e.src_id in first
            and e.dst_id in first
            and first[e.src_id].source_id != first[e.dst_id].source_id
            and not covered(first[e.src_id], used)
            and not covered(first[e.dst_id], used)
        }
        return [([first[a], first[b]], note) for (a, b), note in pairs.items()]
    language = "de" if category == "german-legal" else None
    return [
        ([c], "")
        for c in corpus[source]
        if not covered(c, used)
        and c.meta.get("kind") != "overview"
        # One language per unit: German for German legal questions, otherwise the unit's own
        # first language (German laws are German only).
        and (c.language == language if language else c.language == "en" or source in GERMAN_LAWS)
    ]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def draft_one(
    llm: ChatModel, category: str, units: list[Chunk], note: str
) -> dict[str, Any] | None:
    language = units[0].language
    sources = "\n\n".join(f"Source {u.native_id} ({u.title}):\n{u.text[:3000]}" for u in units)
    reply = await complete(
        llm,
        [{"role": "user", "content": f"{sources}\n\n{note}".strip()}],
        PROMPT.format(kind=KINDS[category], language="German" if language == "de" else "English"),
    )
    found = re.search(r"\{.*\}", reply, re.DOTALL)
    try:
        draft = json.loads(found.group()) if found else {}
    except json.JSONDecodeError:
        draft = {}
    question, facts = draft.get("question"), draft.get("key_facts")
    if not isinstance(question, str) or not isinstance(facts, list) or not facts:
        return None
    if category == "freshness" and units[0].native_id.lower() in question.lower():
        return None  # it was asked not to name the id: retrieval would be trivial
    return {
        "id": f"draft-{category}-{'-'.join(slug(u.native_id) for u in units)}",
        "category": category,
        "split": "test",
        "language": language,
        "question": question,
        "gold_ids": [u.native_id for u in units],
        "key_facts": [str(f) for f in facts],
        "needs_review": True,
    }


async def main(
    settings: Settings,
    source: str,
    category: str,
    n: int,
    seed: int = 0,
    llm: ChatModel | None = None,
) -> int:
    pool = candidates(settings, source, category)
    if not pool:
        print(f"{source}: no unasked units fit {category}")
        return 1
    picked = random.Random(seed).sample(pool, min(n, len(pool)))  # noqa: S311 (sampling)
    llm = llm or judge_model(settings)
    gate = asyncio.Semaphore(4)

    async def one(units: list[Chunk], note: str) -> dict[str, Any] | None:
        async with gate:
            return await draft_one(llm, category, units, note)

    # A failed request must not discard the drafts the others already paid for.
    results = await asyncio.gather(*(one(*p) for p in picked), return_exceptions=True)
    failed = [r for r in results if isinstance(r, BaseException)]
    drafts = [r for r in results if isinstance(r, dict)]
    with DRAFTS.open("a") as out:
        out.writelines(json.dumps(d, ensure_ascii=False) + "\n" for d in drafts)
    if failed:
        print(f"{len(failed)} of {len(picked)} requests failed, e.g. {failed[0]!r}")
    print(
        f"{len(drafts)} of {len(picked)} drafts appended to {DRAFTS.name}: "
        "review them, then move them to golden.jsonl"
    )
    return 0 if drafts and not failed else 1
