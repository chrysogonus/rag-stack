"""How far to trust the judge: a person labels the correctness of sampled answers, then the
configured judge scores the same answers and the two are compared.

The sheet keeps each answer's text and, for RAG answers, the passages the judge saw, so the
judge is checked with exactly what it gets in the eval. It stays valid when results.json is
rewritten and can check a new judge model or rubric against the same human labels."""

import asyncio
import json
import random
from collections import defaultdict
from typing import Any

from rag_stack.agent.answer import FOOTER_START
from rag_stack.config import Settings
from rag_stack.evals.harness import CATEGORIES, DATASET, judge, judge_model, load_cases
from rag_stack.llm.base import ChatModel
from rag_stack.retrieval.retriever import Retriever, open_knowledge_base

LABELS = DATASET / "judge_labels.jsonl"
# Per category: RAG answers and baseline answers, so both sides of the comparison are checked.
PER_CATEGORY = {"rag": 3, "baseline": 2}


async def passages(kb: Retriever, case: dict, result: dict, top_k: int) -> list[dict]:
    """The passages the judge saw for a RAG answer, retrieved again (retrieval is
    deterministic), in the form `judge` reads. Refuses if retrieval no longer matches the run."""
    found = await kb.retrieve(case["question"], context=case.get("follow_up_of", ""))
    if list(dict.fromkeys(r.chunk.native_id for r in found))[:10] != result["retrieved"]:
        raise ValueError(f"{result['id']}: retrieval changed since the eval run; run `make eval`")
    return [
        {"native_id": r.chunk.native_id, "meta": {"relation": r.chunk.meta.get("relation")},
         "text": r.chunk.text}
        for r in found[:top_k]
    ]  # fmt: skip


async def write_sheet(settings: Settings, kb: Retriever | None = None, seed: int = 0) -> int:
    """Sample answers from results.json into a sheet to label; never overwrites labels."""
    if LABELS.exists():
        print(f"{LABELS.name} exists: label it, or delete it to draw a new sample")
        return 1
    kb = kb or await asyncio.to_thread(open_knowledge_base, settings)
    results = json.loads((DATASET / "results.json").read_text())
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r)
    rng = random.Random(seed)  # noqa: S311 (sampling)
    cases = {c["id"]: c for c in load_cases()}
    rows = []
    for category in CATEGORIES:
        for kind, n in PER_CATEGORY.items():
            for r in rng.sample(by_category[category], min(n, len(by_category[category]))):
                answer = r["answer"] if kind == "rag" else r["baseline_answer"]
                case = cases[r["id"]]
                seen = (
                    await passages(kb, case, r, settings.retrieval_top_k) if kind == "rag" else None
                )
                rows.append(
                    {
                        "id": f"{r['id']}:{kind}",
                        "previous_question": case.get("follow_up_of"),
                        "question": case["question"],
                        "key_facts": case["key_facts"],
                        "answer": answer.split(FOOTER_START, 1)[0],
                        # What the judge saw with a RAG answer; the baseline answers without.
                        "sources": seen,
                        # 1-5 by the rubric in evals/rubrics/judge_v1.md; null = not labeled.
                        "correctness": None,
                    }
                )
    rng.shuffle(rows)  # RAG and baseline answers mixed, categories interleaved
    LABELS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} answers written to {LABELS.name}: set each correctness to 1-5")
    return 0


async def agreement(settings: Settings, llm: ChatModel | None = None) -> int:
    """Judge the labeled answers again and compare with the labels (one call per label)."""
    rows = [json.loads(line) for line in LABELS.read_text().splitlines() if line]
    labeled = [r for r in rows if r["correctness"] is not None]
    if not labeled:
        print(f"no labels in {LABELS.name} yet")
        return 1
    if bad := [r["id"] for r in labeled if r["correctness"] not in (1, 2, 3, 4, 5)]:
        raise ValueError(f"correctness must be 1-5: {bad}")
    llm = llm or judge_model(settings)
    gate = asyncio.Semaphore(4)

    async def score(row: dict[str, Any]) -> float:
        case = {k: row[k] for k in ("id", "question", "key_facts")}
        if row["previous_question"]:
            case["follow_up_of"] = row["previous_question"]
        async with gate:
            verdict = await judge(llm, case, row["answer"], row["sources"])
        return verdict["correctness"] * 4 + 1  # back to the rubric's 1-5

    judged = await asyncio.gather(*(score(r) for r in labeled))
    differences = [j - r["correctness"] for j, r in zip(judged, labeled, strict=True)]
    n = len(differences)
    print(f"judge `{settings.eval_judge_model}` vs. human correctness, {n} answers:")
    print(f"  exact {sum(d == 0 for d in differences) / n:.2f}")
    print(f"  within one point {sum(abs(d) <= 1 for d in differences) / n:.2f}")
    print(f"  mean judge minus human {sum(differences) / n:+.2f} points")
    for d, r in sorted(zip(differences, labeled, strict=True), key=lambda p: -abs(p[0])):
        if abs(d) >= 2:
            print(f"  {d:+.0f} {r['id']}")
    return 0
