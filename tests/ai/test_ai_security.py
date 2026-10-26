"""Thresholds on the golden set, checked on the results `make eval` wrote.

A full golden-set run costs about 550 paid LLM calls, so only `make eval` runs it, and it asks
only the questions whose inputs changed. This test checks its saved results, and only if no
question is stale (see `stale_questions` in rag_stack.evals.harness): that check retrieves for
every question, so it needs the indexed knowledge base but no model calls."""

import json

import pytest
import yaml

from rag_stack.evals.harness import (
    DATASET,
    check_thresholds,
    load_cases,
    missing_gold_ids,
    stale_questions,
    summarize,
)
from rag_stack.retrieval.retriever import open_knowledge_base

pytestmark = [pytest.mark.ai, pytest.mark.anyio]


async def test_golden_set_meets_thresholds(settings):
    kb = open_knowledge_base(settings)
    # `make eval` refuses such an index; a gold ID outside every ranking changes no saved result.
    assert missing_gold_ids(kb, load_cases()) == [], "gold IDs missing from the index"
    if stale := await stale_questions(settings, kb):
        pytest.fail(
            f"Saved eval results are stale for {len(stale)} questions ({', '.join(stale[:5])}"
            f"{', ...' if len(stale) > 5 else ''}): run `make eval` (about 2 LLM calls per "
            "stale question), then `make evals`."
        )

    summary = summarize(json.loads((DATASET / "results.json").read_text()))

    for category, scores in summary.items():
        print(category, {k: None if v is None else round(v, 2) for k, v in scores.items()})
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    assert check_thresholds(summary, thresholds) == []
