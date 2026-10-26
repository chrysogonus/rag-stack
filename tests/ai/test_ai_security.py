"""Thresholds on the golden set, checked on the results `make eval` wrote.

The golden set costs about 150 paid LLM calls per run, so only `make eval` runs it. This test
checks its saved results, and only if they were produced by the current code, rubric,
questions, corpus and model settings (see `fingerprint` in rag_stack.evals.harness)."""

import json

import pytest
import yaml

from rag_stack.evals.harness import DATASET, check_thresholds, stale_reasons, summarize

pytestmark = pytest.mark.ai


def test_golden_set_meets_thresholds(settings):
    if reasons := stale_reasons(settings):
        pytest.fail(
            f"Saved eval results are stale ({', '.join(reasons)}): run `make eval` "
            "(one paid golden run, ~280 LLM calls with saved baseline answers), then `make evals`."
        )

    summary = summarize(json.loads((DATASET / "results.json").read_text()))

    for category, scores in summary.items():
        print(category, {k: None if v is None else round(v, 2) for k, v in scores.items()})
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    assert check_thresholds(summary, thresholds) == []
