import json

import pytest
from fakes.embeddings import chunk

from rag_stack.evals.harness import (
    CATEGORIES,
    DATASET,
    check_thresholds,
    citations,
    load_cases,
    summarize,
)
from rag_stack.evals.metrics import citation_precision, mean, mrr, recall_at_k


def test_recall_and_mrr_count_distinct_ids():
    ranked = ["A", "A", "B", "C", "D"]

    assert recall_at_k(ranked, ["B", "D"], k=3) == 0.5
    assert recall_at_k(ranked, ["B", "D"], k=10) == 1.0
    assert mrr(ranked, ["C"]) == pytest.approx(1 / 3)
    assert mrr(ranked, ["Z"]) == 0.0


def test_citation_precision_and_mean():
    assert citation_precision(["A", "B"], ["A"]) == 0.5
    assert citation_precision([], ["A"]) == 0.0
    assert mean([1.0, None, 0.0]) == 0.5
    assert mean([None]) is None


def test_citations_read_links_to_sources_and_normalize_bracketed_ids():
    m0019 = chunk("AML.M0019")
    text = f"Per [Article 50(1)] and [AML.T0051, AML.M0019], see [Access control]({m0019.url})."

    assert citations(text, [m0019]) == ["AML.M0019", "AI Act Art. 50(1)", "AML.T0051"]


def test_summary_and_thresholds():
    results = [
        {"category": "cve", "recall_at_10": 1.0, "mrr": 1.0, "correctness": 0.5},
        {"category": "abstention", "recall_at_10": None, "mrr": None, "correctness": 1.0},
    ]
    for r in results:
        for metric in ("citation_precision", "baseline_citation_precision", "faithfulness"):
            r[metric] = None
        r |= {"abstention_accuracy": 1.0, "baseline_abstention_accuracy": 0.0}
        r["baseline_correctness"] = 0.0

    summary = summarize(results)

    assert summary["all"]["recall_at_10"] == 1.0
    assert summary["all"]["correctness"] == 0.75
    assert check_thresholds(summary, {"correctness": 0.7, "mrr": 0.5}) == []
    assert check_thresholds(summary, {"correctness": 0.8}) == ["correctness: 0.75 < 0.8"]
    assert check_thresholds(summary, {"faithfulness": 0.5}) == ["faithfulness: None < 0.5"]


def test_golden_set_has_the_required_shape():
    cases = load_cases()
    counts = {c: sum(case["category"] == c for case in cases) for c in CATEGORIES}

    assert counts == {
        "id-exact": 10,
        "freshness": 10,
        "cross-source": 10,
        "german-legal": 10,
        "cve": 5,
        "list": 5,
        "abstention": 5,
    }
    assert len({case["id"] for case in cases}) == 55
    for case in cases:
        assert case["language"] in ("en", "de"), case["id"]
        assert case["needs_review"] is True, case["id"]
        assert case["key_facts"], case["id"]
        assert bool(case["gold_ids"]) != (case["category"] == "abstention"), case["id"]
    assert all(case["language"] == "de" for case in cases if case["category"] == "german-legal")
    json.dumps(cases)  # plain JSON throughout
    assert (DATASET / "thresholds.yaml").exists()


def test_baseline_defaults_to_the_rag_model_and_can_be_a_separate_chatbot():
    from rag_stack.config import Settings
    from rag_stack.evals.harness import baseline_model, baseline_name
    from rag_stack.llm.openai_compatible import OpenAICompatibleModel

    plain = Settings(llm_model="gpt-6-astra")
    assert baseline_model(plain) is None
    assert baseline_name(plain) == (
        "the same model (`gpt-6-astra`) and questions without retrieval"
    )

    live = Settings(
        eval_baseline_provider="openai-compatible",
        eval_baseline_base_url="http://127.0.0.1:11435/v1",
        eval_baseline_model="codex/gpt-6-luna",
    )
    assert isinstance(baseline_model(live), OpenAICompatibleModel)
    assert "`codex/gpt-6-luna` (openai-compatible) as a general chatbot" in baseline_name(live)


def test_saved_results_are_stale_when_anything_they_depend_on_changes(tmp_path, monkeypatch):
    import shutil

    from rag_stack.config import Settings
    from rag_stack.evals import harness

    shutil.copy(DATASET / "golden.jsonl", tmp_path / "golden.jsonl")
    monkeypatch.setattr(harness, "DATASET", tmp_path)
    settings = Settings(data_dir=str(tmp_path / "data"), llm_model="gpt-6-astra")

    assert harness.stale_reasons(settings) == ["no results with a fingerprint"]

    (tmp_path / "results.json").write_text("[]")
    (tmp_path / "fingerprint.json").write_text(json.dumps(harness.fingerprint(settings)))
    assert harness.stale_reasons(settings) == []

    assert harness.stale_reasons(settings.model_copy(update={"llm_model": "gpt-6-luna"})) == [
        "settings changed"
    ]
    (tmp_path / "golden.jsonl").write_text("{}\n")
    assert harness.stale_reasons(settings) == ["golden changed"]
