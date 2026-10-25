import json

import pytest
from fakes.embeddings import chunk

from rag_stack.evals.harness import (
    CATEGORIES,
    DATASET,
    SPLITS,
    check_thresholds,
    citations,
    load_cases,
    summarize,
)
from rag_stack.evals.metrics import bootstrap_ci, citation_precision, mean, mrr, recall_at_k


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


def test_bootstrap_ci_brackets_the_mean_and_is_reproducible():
    values = [1.0, 0.0, 1.0, 1.0, None]

    interval = bootstrap_ci(values)
    assert interval is not None
    low, high = interval

    assert 0.0 <= low < 0.75 < high <= 1.0
    assert bootstrap_ci(values) == (low, high)
    assert bootstrap_ci([1.0, 1.0]) == (1.0, 1.0)
    assert bootstrap_ci([None]) is None


def test_citations_read_links_to_sources_and_normalize_bracketed_ids():
    m0019 = chunk("AML.M0019")
    text = f"Per [Article 50(1)] and [AML.T0051, AML.M0019], see [Access control]({m0019.url})."

    assert citations(text, [m0019]) == ["AML.M0019", "AI Act Art. 50(1)", "AML.T0051"]


def test_summary_and_thresholds():
    results = [
        {"category": "cve", "split": "test", "recall_at_10": 1.0, "mrr": 1.0, "correctness": 0.5},
        {"category": "cve", "split": "test", "recall_at_10": None, "mrr": None, "correctness": 1.0},
        {"category": "list", "split": "dev", "recall_at_10": 0.0, "mrr": 0.0, "correctness": 0.0},
    ]
    for r in results:
        for metric in ("citation_precision", "baseline_citation_precision", "faithfulness"):
            r[metric] = None
        r |= {"abstention_accuracy": 1.0, "baseline_abstention_accuracy": 0.0}
        r["baseline_correctness"] = 0.0

    summary = summarize(results)

    assert summary["test"]["recall_at_10"] == 1.0
    assert summary["test"]["correctness"] == 0.75
    assert summary["all"]["correctness"] == 0.5
    assert summary["cve"] == summary["test"]
    # Thresholds apply to the test split: the failing dev case doesn't count.
    assert check_thresholds(summary, {"correctness": 0.7, "mrr": 0.5}) == []
    assert check_thresholds(summary, {"correctness": 0.8}) == ["correctness: 0.75 < 0.8"]
    assert check_thresholds(summary, {"faithfulness": 0.5}) == ["faithfulness: None < 0.5"]
    assert check_thresholds(summary, {"mrr": 0.6}, row="dev") == ["mrr: 0.0 < 0.6"]
    # Until the holdout has questions, thresholds apply to dev.
    assert check_thresholds(summarize(results[2:]), {"mrr": 0.6}) == ["mrr: 0.0 < 0.6"]


def test_golden_set_has_the_required_shape():
    cases = load_cases()
    counts = {c: sum(case["category"] == c for case in cases) for c in CATEGORIES}

    # At least the original set; reviewed drafts add to it.
    minimum = {
        "id-exact": 10,
        "freshness": 10,
        "cross-source": 10,
        "german-legal": 10,
        "cve": 5,
        "list": 5,
        "abstention": 6,
        "follow-up": 3,
    }
    assert all(counts[c] >= n for c, n in minimum.items()), counts
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["language"] in ("en", "de"), case["id"]
        assert isinstance(case["needs_review"], bool), case["id"]
        assert case["key_facts"], case["id"]
        assert bool(case["gold_ids"]) != (case["category"] == "abstention"), case["id"]
        assert ("follow_up_of" in case) >= (case["category"] == "follow-up"), case["id"]
        assert case["split"] in SPLITS, case["id"]
    # Questions with the same answer (a paraphrase, a translation) share a split, or tuning on
    # one would leak into the score of the other.
    splits: dict[tuple, set[str]] = {}
    for case in cases:
        splits.setdefault((case["category"], *case["gold_ids"]), set()).add(case["split"])
    assert all(len(found) == 1 for key, found in splits.items() if key[1:]), splits
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


def test_judge_defaults_to_the_rag_provider_and_can_run_elsewhere():
    from pydantic import SecretStr

    from rag_stack.config import Settings
    from rag_stack.evals.harness import judge_model
    from rag_stack.llm.openai_compatible import OpenAICompatibleModel
    from rag_stack.llm.openai_responses import OpenAIResponsesModel

    assert isinstance(judge_model(Settings(llm_api_key=SecretStr("k"))), OpenAIResponsesModel)

    gateway = judge_model(
        Settings(
            eval_judge_provider="openai-compatible",
            eval_judge_base_url="http://127.0.0.1:11435/v1",
            eval_judge_model="codex/gpt-6-luna",
        )
    )
    assert isinstance(gateway, OpenAICompatibleModel)
    assert str(gateway._client.base_url) == "http://127.0.0.1:11435/v1/"
    assert gateway._model == "codex/gpt-6-luna"


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


def test_tools_that_never_run_in_the_eval_leave_its_code_hash_alone(tmp_path, monkeypatch):
    import shutil

    from rag_stack.config import Settings
    from rag_stack.evals import harness

    for tool in harness.NOT_IN_EVAL:
        assert (harness.ROOT / tool).exists(), tool  # not a stale name
    shutil.copytree(harness.ROOT / "src", tmp_path / "src")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    settings = Settings(data_dir=str(tmp_path / "data"))
    code = lambda: harness.fingerprint(settings)["code"]  # noqa: E731
    before = code()

    for tool in harness.NOT_IN_EVAL:
        with (tmp_path / tool).open("a") as f:
            f.write("\n# edited\n")
    assert code() == before
    with (tmp_path / "src/rag_stack/agent/prompts.py").open("a") as f:
        f.write("\n# edited\n")
    assert code() != before


@pytest.mark.anyio
async def test_a_follow_up_case_asks_its_previous_question_first_in_the_same_thread():
    from fakes.embeddings import FakeRetriever
    from fakes.llm import FakeChatModel
    from langgraph.checkpoint.memory import InMemorySaver

    from rag_stack.agent.graph import build_graph
    from rag_stack.config import Settings
    from rag_stack.evals.harness import run_case

    settings = Settings()
    rag = FakeChatModel("AML.T0051 is LLM Prompt Injection.", "Use guardrails [AML.M0020].")
    graph = build_graph(rag, InMemorySaver(), settings, FakeRetriever(chunk("AML.M0020")))
    baseline = FakeChatModel("It is prompt injection.", "Use guardrails.")
    verdict = '{"correctness": 5, "faithfulness": 5, "reason": "ok"}'
    judge = FakeChatModel(verdict, verdict)
    case = {
        "id": "f",
        "category": "follow-up",
        "split": "dev",
        "follow_up_of": "What is AML.T0051?",
        "question": "How do I defend against it?",
        "gold_ids": ["AML.M0020"],
        "key_facts": ["Guardrails"],
    }

    result = await run_case(case, settings, graph, baseline, judge)

    asked = [m["content"] for m in rag.calls[1]["messages"] if m["role"] == "user"]
    assert asked[0] == "What is AML.T0051?"
    assert asked[-1].endswith("How do I defend against it?")
    assert [m["content"] for m in baseline.calls[1]["messages"]] == [
        "What is AML.T0051?",
        "It is prompt injection.",
        "How do I defend against it?",
    ]
    assert json.loads(judge.calls[0]["messages"][0]["content"])["previous_question"] == (
        "What is AML.T0051?"
    )
    assert result["recall_at_10"] == 1.0


@pytest.mark.anyio
async def test_retrieval_only_scores_the_golden_set_without_an_llm(capsys):
    from rag_stack.config import Settings
    from rag_stack.evals.harness import retrieval_only
    from rag_stack.retrieval.retriever import Retrieved

    class Perfect:
        """Finds exactly the gold IDs of whichever case is asked."""

        def __init__(self) -> None:
            self.asked: list[tuple[str, str]] = []
            self.gold = {
                (c["question"], c.get("follow_up_of", "")): c["gold_ids"] for c in load_cases()
            }

        async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
            self.asked.append((query, context))
            return [Retrieved(chunk(i), 1.0, "id") for i in self.gold[(query, context)]]

        async def catalog(self) -> list[str]:
            return []

    kb = Perfect()
    assert await retrieval_only(Settings(), kb) == 0
    assert ("How do I defend against it?", "What is AML.T0051?") in kb.asked
    out = capsys.readouterr().out
    assert out.startswith("split: dev")
    assert "all            recall@10 1.000  mrr 1.000" in out

    # Only the asked split is retrieved: dev and test questions don't mix.
    dev = set(kb.asked)
    assert await retrieval_only(Settings(), kb, split="test") == 0
    assert kb.asked[len(dev) :] and dev.isdisjoint(kb.asked[len(dev) :])


@pytest.mark.anyio
async def test_retrieval_only_fails_on_a_split_without_questions(capsys, monkeypatch):
    from fakes.embeddings import FakeRetriever

    from rag_stack.config import Settings
    from rag_stack.evals import harness

    monkeypatch.setattr(harness, "load_cases", lambda: [{"split": "dev", "gold_ids": ["A"]}])
    kb = FakeRetriever()

    assert await harness.retrieval_only(Settings(), kb, split="test") == 1
    assert kb.calls == []
    assert "split test: no questions" in capsys.readouterr().out
