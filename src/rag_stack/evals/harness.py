"""Golden-set eval: the RAG chatbot against the same LLM without retrieval (a stand-in for a
general chatbot). Writes report.md and results.json next to the dataset."""

import asyncio
import hashlib
import json
import re
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from rag_stack.agent.answer import FOOTER_START, cited_ids, is_abstention
from rag_stack.agent.graph import build_graph
from rag_stack.agent.prompts import ABSTAIN, BASELINE_PROMPT
from rag_stack.config import Settings
from rag_stack.evals.metrics import citation_precision, mean, mrr, recall_at_k
from rag_stack.ingestion.models import Chunk
from rag_stack.llm.base import ChatModel, Message, TextDelta
from rag_stack.llm.factory import create_chat_model
from rag_stack.retrieval.ids import detect_ids
from rag_stack.retrieval.retriever import KnowledgeBase, Retriever, open_knowledge_base

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "evals/datasets/ai_security"
RUBRIC = ROOT / "evals/rubrics/judge_v1.md"
CATEGORIES = [
    "id-exact",
    "freshness",
    "cross-source",
    "german-legal",
    "cve",
    "list",
    "abstention",
    "follow-up",
]
METRICS = [
    "recall_at_10",
    "mrr",
    "citation_precision",
    "baseline_citation_precision",
    "abstention_accuracy",
    "baseline_abstention_accuracy",
    "faithfulness",
    "correctness",
    "baseline_correctness",
]
ID_LIKE = re.compile(r"\[([^\[\]\n]{2,60})\]")


def load_cases(dataset: Path = DATASET) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in (dataset / "golden.jsonl").read_text().splitlines() if line
    ]


async def complete(llm: ChatModel, messages: list[Message], instructions: str) -> str:
    parts = [
        event.text
        async for event in llm.stream(messages, instructions=instructions, max_output_tokens=4096)
        if isinstance(event, TextDelta)
    ]
    return "".join(parts)


def citations(text: str, sources: list[Chunk]) -> list[str]:
    """IDs an answer cites: links to its sources, plus anything ID-like in brackets (normalized,
    so a baseline's [Article 50(1)] counts as AI Act Art. 50(1))."""
    found = cited_ids(text, sources)
    found += [i for group in ID_LIKE.findall(text) for i in detect_ids(group)]
    return list(dict.fromkeys(found))


async def judge(llm: ChatModel, case: dict, answer: str, sources: list[dict] | None) -> dict:
    payload = {
        **({"previous_question": case["follow_up_of"]} if "follow_up_of" in case else {}),
        "question": case["question"],
        "key_facts": case["key_facts"],
        "answer": answer,
        "sources": [
            {"id": s["native_id"], "relation": s["meta"].get("relation"), "text": s["text"][:3000]}
            for s in sources
        ]
        if sources is not None
        else None,
    }
    reply = await complete(
        llm,
        [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        RUBRIC.read_text(),
    )
    # Take the first {...} block: some models wrap the JSON in prose or a code fence.
    found = re.search(r"\{.*\}", reply, re.DOTALL)
    if not found:
        raise ValueError(f"{case['id']}: judge returned no JSON: {reply!r}")
    verdict = json.loads(found.group())
    scale = lambda v: None if v is None else (float(v) - 1) / 4  # noqa: E731
    return {
        "correctness": scale(verdict["correctness"]),
        "faithfulness": scale(verdict.get("faithfulness")),
        "reason": verdict.get("reason", ""),
    }


def baseline_model(settings: Settings) -> ChatModel | None:
    """The configured reference chatbot, or None to use the RAG model without retrieval."""
    if not settings.eval_baseline_provider:
        return None
    return create_chat_model(
        settings.eval_baseline_provider,
        settings.eval_baseline_model or settings.llm_model,
        api_key=settings.eval_baseline_api_key.get_secret_value(),
        base_url=settings.eval_baseline_base_url,
    )


def judge_model(settings: Settings) -> ChatModel:
    """The judge, on its own provider if one is set, otherwise on the RAG model's."""
    if not settings.eval_judge_provider:
        return create_chat_model(
            settings.llm_provider,
            settings.eval_judge_model,
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
        )
    return create_chat_model(
        settings.eval_judge_provider,
        settings.eval_judge_model,
        api_key=settings.eval_judge_api_key.get_secret_value(),
        base_url=settings.eval_judge_base_url,
    )


def baseline_name(settings: Settings) -> str:
    if not settings.eval_baseline_provider:
        return f"the same model (`{settings.llm_model}`) and questions without retrieval"
    model = settings.eval_baseline_model or settings.llm_model
    return f"`{model}` ({settings.eval_baseline_provider}) as a general chatbot, same questions"


async def run_case(
    case: dict, settings: Settings, graph, baseline_llm: ChatModel, judge_llm: ChatModel
) -> dict:
    expect_abstain = case["category"] == "abstention"
    gold = case["gold_ids"]
    # A follow-up case asks its previous question first, in the same thread for both bots.
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    history: list[Message] = []
    if previous := case.get("follow_up_of"):
        await graph.ainvoke({"messages": [{"role": "user", "content": previous}]}, config)
        history = [{"role": "user", "content": previous}]
        history.append(
            {"role": "assistant", "content": await complete(baseline_llm, history, BASELINE_PROMPT)}
        )
    state = await graph.ainvoke(
        {"messages": [{"role": "user", "content": case["question"]}]}, config
    )
    full = state["messages"][-1]["content"]
    ranked = [s["native_id"] for s in state["sources"]]
    chunks = [Chunk.model_validate(s) for s in state["sources"][: settings.retrieval_top_k]]
    body = full.split(FOOTER_START, 1)[0]
    baseline = await complete(
        baseline_llm, [*history, {"role": "user", "content": case["question"]}], BASELINE_PROMPT
    )

    rag_verdict, base_verdict = await asyncio.gather(
        judge(judge_llm, case, body, state["sources"][: settings.retrieval_top_k]),
        judge(judge_llm, case, baseline, None),
    )
    rag_abstained, base_abstained = is_abstention(body), baseline.strip().startswith(ABSTAIN)
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "gold_ids": gold,
        "retrieved": list(dict.fromkeys(ranked))[:10],
        "recall_at_10": None if expect_abstain else recall_at_k(ranked, gold),
        "mrr": None if expect_abstain else mrr(ranked, gold),
        "citation_precision": None
        if expect_abstain
        else citation_precision(citations(body, chunks), gold),
        "baseline_citation_precision": None
        if expect_abstain
        else citation_precision(citations(baseline, []), gold),
        "abstention_accuracy": float(rag_abstained == expect_abstain),
        "baseline_abstention_accuracy": float(base_abstained == expect_abstain),
        "faithfulness": rag_verdict["faithfulness"],
        "correctness": rag_verdict["correctness"],
        "baseline_correctness": base_verdict["correctness"],
        "judge_reason": rag_verdict["reason"],
        "baseline_judge_reason": base_verdict["reason"],
        "answer": full,
        "baseline_answer": baseline,
    }


async def run(
    settings: Settings, kb: KnowledgeBase | None = None, concurrency: int = 4
) -> list[dict]:
    kb = kb or await asyncio.to_thread(open_knowledge_base, settings)
    cases = load_cases()
    missing = await asyncio.to_thread(missing_gold_ids, kb, cases)
    if missing:
        raise ValueError(f"gold IDs not in the index: {missing}")

    llm = create_chat_model(
        settings.llm_provider,
        settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
    )
    judge_llm = judge_model(settings)
    baseline_llm = baseline_model(settings) or llm
    graph = build_graph(llm, InMemorySaver(), settings, kb)
    gate = asyncio.Semaphore(concurrency)

    async def one(case: dict) -> dict:
        async with gate:
            return await run_case(case, settings, graph, baseline_llm, judge_llm)

    return await asyncio.gather(*(one(case) for case in cases))


def missing_gold_ids(kb: KnowledgeBase, cases: list[dict]) -> list[str]:
    gold = sorted({g for case in cases for g in case["gold_ids"]})
    found = {c.native_id for c in kb.by_ids(gold)}
    return [g for g in gold if g not in found]


def summarize(results: list[dict]) -> dict[str, dict[str, float | None]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[r["category"]].append(r)
    groups["all"] = results
    return {name: {m: mean([r[m] for r in rows]) for m in METRICS} for name, rows in groups.items()}


def check_thresholds(summary: dict[str, dict[str, float | None]], thresholds: dict) -> list[str]:
    failures = []
    for metric, minimum in thresholds.items():
        value = summary["all"][metric]
        if value is None or value < minimum:
            failures.append(f"{metric}: {value} < {minimum}")
    return failures


def report(results: list[dict], settings: Settings) -> str:
    summary = summarize(results)
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"  # noqa: E731
    counts = {c: sum(r["category"] == c for r in results) for c in CATEGORIES}
    header = (
        "| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision "
        "(base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for name in [*CATEGORIES, "all"]:
        s = summary.get(name)
        if not s:
            continue
        rows.append(
            f"| {name} | {counts.get(name, len(results))} "
            f"| {fmt(s['recall_at_10'])} | {fmt(s['mrr'])} "
            f"| {fmt(s['baseline_correctness'])} → {fmt(s['correctness'])} "
            f"| {fmt(s['baseline_citation_precision'])} → {fmt(s['citation_precision'])} "
            f"| {fmt(s['baseline_abstention_accuracy'])} → {fmt(s['abstention_accuracy'])} "
            f"| {fmt(s['faithfulness'])} |"
        )
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    failures = check_thresholds(summary, thresholds)
    status = "all thresholds met" if not failures else "FAILED: " + "; ".join(failures)
    return (
        "# Eval report: AI-security golden set\n\n"
        f"Chat model `{settings.llm_model}` ({settings.llm_provider}); judge "
        f"`{settings.eval_judge_model}` ({settings.eval_judge_provider or settings.llm_provider}) "
        f"with rubric `{RUBRIC.relative_to(ROOT)}`. Baseline: "
        f"{baseline_name(settings)}. Scores are means in [0, 1]; judge scores "
        "map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions.\n\n"
        f"Thresholds (`thresholds.yaml`, on the `all` row): {status}.\n\n"
        + header
        + "\n".join(rows)
        + "\n\nPer-question results, answers and judge reasons: `results.json`. The questions are "
        "drafts (`needs_review: true`) generated from the indexed corpus.\n"
    )


def corpus_manifest(settings: Settings) -> list[dict]:
    """Which snapshot of each source the eval ran against (the corpus itself is not committed)."""
    entries = []
    for manifest in sorted(Path(settings.data_dir).glob("raw/*/*/manifest.json")):
        data = json.loads(manifest.read_text())
        latest = Path(settings.data_dir) / "processed" / data["source_id"] / "LATEST"
        if latest.exists() and latest.read_text().strip() == manifest.parent.name:
            entries.append({k: data[k] for k in ("source_id", "version", "sha256", "retrieved_at")})
    return entries


# Settings that change answers or scores; secrets and limits are left out.
FINGERPRINT_SETTINGS = (
    "llm_provider",
    "llm_base_url",
    "llm_model",
    "eval_judge_model",
    "eval_judge_provider",
    "eval_judge_base_url",
    "eval_baseline_provider",
    "eval_baseline_base_url",
    "eval_baseline_model",
    "qdrant_collection",
    "embedding_model",
    "sparse_model",
    "reranker_model",
    "rerank_max_chars",
    "rerank_min_score",
    "retrieval_candidates",
    "retrieval_top_k",
    "max_chunk_chars",
    "max_output_tokens",
)


def fingerprint(settings: Settings) -> dict[str, str]:
    """What a results.json depends on: code, rubric, questions, corpus snapshot, model settings.
    Results whose fingerprint differs from the current one say nothing about the current code."""
    code = hashlib.sha256()
    for path in sorted((ROOT / "src/rag_stack").rglob("*.py")):
        code.update(path.relative_to(ROOT).as_posix().encode() + path.read_bytes())
    corpus = hashlib.sha256()
    for latest in sorted(Path(settings.data_dir).glob("processed/*/LATEST")):
        processed = latest.parent / latest.read_text().strip() / "sha256"
        corpus.update(latest.parent.name.encode() + processed.read_bytes())
    config = {name: str(getattr(settings, name)) for name in FINGERPRINT_SETTINGS}
    return {
        "code": code.hexdigest(),
        "rubric": hashlib.sha256(RUBRIC.read_bytes()).hexdigest(),
        "golden": hashlib.sha256((DATASET / "golden.jsonl").read_bytes()).hexdigest(),
        "corpus": corpus.hexdigest(),
        "settings": json.dumps(config, sort_keys=True),
    }


def stale_reasons(settings: Settings) -> list[str]:
    """Why the saved results don't describe the current setup; empty if they do."""
    saved = DATASET / "fingerprint.json"
    if not (DATASET / "results.json").exists() or not saved.exists():
        return ["no results with a fingerprint"]
    old, new = json.loads(saved.read_text()), fingerprint(settings)
    return [f"{key} changed" for key in new if old.get(key) != new[key]]


async def retrieval_only(settings: Settings, kb: Retriever | None = None) -> int:
    """Recall@10, MRR and retrieval time on the golden set, with no LLM calls and no files
    written: a quick loop for tuning retrieval settings against the thresholds."""
    kb = kb or await asyncio.to_thread(open_knowledge_base, settings)
    rows = []
    for case in load_cases():
        if not case["gold_ids"]:
            continue
        start = time.perf_counter()
        found = await kb.retrieve(case["question"], context=case.get("follow_up_of", ""))
        ranked = [r.chunk.native_id for r in found]
        rows.append(
            {
                "category": case["category"],
                "seconds": time.perf_counter() - start,
                "recall_at_10": recall_at_k(ranked, case["gold_ids"]),
                "mrr": mrr(ranked, case["gold_ids"]),
            }
        )
    summary = {}
    for name in [*CATEGORIES, "all"]:
        group = [r for r in rows if name in ("all", r["category"])]
        if group:
            summary[name] = {m: mean([r[m] for r in group]) for m in ("recall_at_10", "mrr")}
            recall, rank = summary[name]["recall_at_10"], summary[name]["mrr"]
            print(f"{name:14} recall@10 {recall:.3f}  mrr {rank:.3f}")
    seconds = sorted(r["seconds"] for r in rows)
    p50, p95 = seconds[len(seconds) // 2], seconds[int(len(seconds) * 0.95)]
    print(f"retrieval p50 {p50:.2f} s, p95 {p95:.2f} s")
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    failed = check_thresholds(summary, {m: thresholds[m] for m in ("recall_at_10", "mrr")})
    print(*failed, sep="\n")
    return 1 if failed else 0


async def main(settings: Settings) -> int:
    results = await run(settings)
    (DATASET / "fingerprint.json").write_text(json.dumps(fingerprint(settings), indent=1) + "\n")
    (DATASET / "corpus").mkdir(exist_ok=True)
    (DATASET / "corpus/manifest.json").write_text(
        json.dumps(corpus_manifest(settings), indent=1) + "\n"
    )
    (DATASET / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    (DATASET / "report.md").write_text(report(results, settings))
    print((DATASET / "report.md").read_text())
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    return 1 if check_thresholds(summarize(results), thresholds) else 0
