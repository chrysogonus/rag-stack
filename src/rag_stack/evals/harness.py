"""Golden-set eval: the RAG chatbot against a baseline chatbot (`EVAL_BASELINE_*`; unset, the
same LLM without retrieval). Writes report.md and results.json next to the dataset."""

import asyncio
import hashlib
import json
import re
import subprocess
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver
from qdrant_client import QdrantClient

from rag_stack import observability
from rag_stack.agent.answer import FOOTER_START, cited_ids, footer, is_abstention
from rag_stack.agent.graph import build_graph, model_input
from rag_stack.agent.prompts import ABSTAIN, BASELINE_PROMPT, SYSTEM_PROMPT
from rag_stack.config import Settings
from rag_stack.evals.metrics import bootstrap_ci, citation_precision, mean, mrr, recall_at_k
from rag_stack.ingestion.models import Chunk
from rag_stack.llm.base import ChatModel, Message, TextDelta
from rag_stack.llm.factory import create_chat_model
from rag_stack.retrieval.ids import detect_ids
from rag_stack.retrieval.language import detect_language
from rag_stack.retrieval.retriever import (
    KnowledgeBase,
    Retrieved,
    Retriever,
    open_knowledge_base,
)

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "evals/datasets/ai_security"
RUBRIC = ROOT / "evals/rubrics/judge_v1.md"
HISTORY = DATASET / "history.jsonl"
# freshness: content first published on or after 2026-01-01, newer than the models' training data;
# paraphrase: older content asked in a user's own words, without its ID; cross-source: needs units
# of two or more sources; relation: follows links within one source (technique → mitigation);
# injection: a source holds an attack payload to describe, not follow; robustness: an ID or
# question in an unusual form (lowercase, spaced, informal, padded, the other language).
CATEGORIES = [
    "id-exact",
    "freshness",
    "paraphrase",
    "cross-source",
    "relation",
    "german-legal",
    "cve",
    "list",
    "abstention",
    "follow-up",
    "injection",
    "robustness",
]
# Tune on dev; test holds reviewed questions no setting was tuned on. Paraphrases and
# translations of a question stay in its split. The first 59 questions were tuned on: all dev.
SPLITS = ["dev", "test"]
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


def judge_input(case: dict, answer: str, sources: list[dict] | None) -> str:
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
    return json.dumps(payload, ensure_ascii=False)


async def judge(llm: ChatModel, case: dict, answer: str, sources: list[dict] | None) -> dict:
    messages: list[Message] = [{"role": "user", "content": judge_input(case, answer, sources)}]
    # Judges now and then reply with broken JSON (an unescaped quote); asking again fixes that.
    reply = ""
    for _ in range(2):
        reply = await complete(llm, messages, RUBRIC.read_text())
        # Take the first {...} block: some models wrap the JSON in prose or a code fence.
        found = re.search(r"\{.*\}", reply, re.DOTALL)
        try:
            verdict = json.loads(found.group()) if found else None
        except json.JSONDecodeError:
            verdict = None
        if verdict is not None:
            break
    else:
        raise ValueError(f"{case['id']}: judge returned no valid JSON twice, last: {reply!r}")
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


def digest(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def baseline_key(settings: Settings, case: dict) -> str:
    """What a baseline answer depends on: a saved answer with the same key is reused, since no
    change to our code or corpus changes it."""
    if settings.eval_baseline_provider:
        model = [
            settings.eval_baseline_provider,
            settings.eval_baseline_base_url,
            settings.eval_baseline_model or settings.llm_model,
        ]
    else:
        model = [settings.llm_provider, settings.llm_base_url, settings.llm_model]
    return digest(model, BASELINE_PROMPT, case.get("follow_up_of"), case["question"])


def judge_key(settings: Settings, case: dict, answer: str, sources: list[dict] | None) -> str:
    """What the judge's verdict on an answer depends on."""
    own = bool(settings.eval_judge_provider)
    judge_llm = [
        settings.eval_judge_provider if own else settings.llm_provider,
        settings.eval_judge_base_url if own else settings.llm_base_url,
        settings.eval_judge_model,
    ]
    return digest(judge_llm, RUBRIC.read_text(), judge_input(case, answer, sources))


async def model_inputs(
    settings: Settings, kb: Retriever, case: dict
) -> tuple[list[list[Message]], list[Retrieved]]:
    """Each turn's model input as the graph builds it, and the last question's ranking. An
    earlier answer is a placeholder: it follows from that turn's input, which is included, so a
    follow-up is stale whenever its previous turn is."""
    questions = [*([case["follow_up_of"]] if "follow_up_of" in case else []), case["question"]]
    messages: list[Message] = []
    turns: list[list[Message]] = []
    found: list[Retrieved] = []
    for n, question in enumerate(questions):
        messages.append({"role": "user", "content": question})
        found = await kb.retrieve(question, context=questions[n - 1] if n else "")
        turns.append(
            model_input(messages, [r.chunk for r in found[: settings.retrieval_top_k]], settings)
        )
        messages.append({"role": "assistant", "content": "(the answer to this input)"})
    return turns, found


def answer_key(settings: Settings, catalog: list[str], turns: list[list[Message]]) -> str:
    """What a RAG answer depends on: the model, its instructions, each turn's input and the
    source names a refusal lists. Code, corpus and settings matter only through these."""
    model = [
        settings.llm_provider,
        settings.llm_base_url,
        settings.llm_model,
        settings.max_output_tokens,
    ]
    return digest(model, SYSTEM_PROMPT, catalog, turns)


def baseline_name(settings: Settings) -> str:
    if not settings.eval_baseline_provider:
        return f"the same model (`{settings.llm_model}`) and questions without retrieval"
    model = settings.eval_baseline_model or settings.llm_model
    return f"`{model}` ({settings.eval_baseline_provider}) as a general chatbot, same questions"


async def run_case(
    case: dict,
    settings: Settings,
    kb: Retriever,
    graph,
    baseline_llm: ChatModel,
    judge_llm: ChatModel,
    saved: dict | None = None,
) -> dict:
    """One golden-set case. `saved` is its result from an earlier run: its answers and verdicts
    are reused while the inputs they depend on are unchanged, so only changed questions cost
    model calls. Retrieval and the scores derived from the answers always run."""
    saved = saved or {}
    expect_abstain = case["category"] == "abstention"
    gold = case["gold_ids"]
    previous = case.get("follow_up_of")
    turns, found = await model_inputs(settings, kb, case)
    rag_key = answer_key(settings, await kb.catalog(), turns)
    rag_reused = saved.get("answer_key") == rag_key
    if rag_reused:
        full = saved["answer"]
        sources = [r.chunk.model_dump() for r in found]
    else:
        # A follow-up case asks its previous question first, in the same thread for both bots.
        config = {"configurable": {"thread_id": str(uuid.uuid4()), "tags": ["eval"]}}
        if previous:
            await graph.ainvoke({"messages": [{"role": "user", "content": previous}]}, config)
        state = await graph.ainvoke(
            {"messages": [{"role": "user", "content": case["question"]}]}, config
        )
        full = state["messages"][-1]["content"]
        sources = state["sources"]
    ranked = [s["native_id"] for s in sources]
    shown = sources[: settings.retrieval_top_k]
    chunks = [Chunk.model_validate(s) for s in shown]
    body = full.split(FOOTER_START, 1)[0]
    if rag_reused and not is_abstention(body):
        # The footer (source versions, attribution) isn't hashed: rebuild it as the graph does.
        full = body + footer(body, chunks, detect_language(case["question"]))
    base_key = baseline_key(settings, case)
    base_reused = saved.get("baseline_key") == base_key
    if base_reused:
        baseline = saved["baseline_answer"]
    else:
        history: list[Message] = []
        if previous:
            history = [{"role": "user", "content": previous}]
            history.append(
                {
                    "role": "assistant",
                    "content": await complete(baseline_llm, history, BASELINE_PROMPT),
                }
            )
        baseline = await complete(
            baseline_llm, [*history, {"role": "user", "content": case["question"]}], BASELINE_PROMPT
        )
    rag_score_key = judge_key(settings, case, body, shown)
    base_score_key = judge_key(settings, case, baseline, None)

    async def verdict(prefix: str, key: str, answer: str, sources: list[dict] | None) -> dict:
        if saved.get(f"{prefix}judge_key") == key:
            return {
                "correctness": saved[f"{prefix}correctness"],
                "faithfulness": saved.get(f"{prefix}faithfulness"),
                "reason": saved[f"{prefix}judge_reason"],
            }
        return await judge(judge_llm, case, answer, sources)

    rag_verdict, base_verdict = await asyncio.gather(
        verdict("", rag_score_key, body, shown),
        verdict("baseline_", base_score_key, baseline, None),
    )
    rag_abstained, base_abstained = is_abstention(body), baseline.strip().startswith(ABSTAIN)
    return {
        "id": case["id"],
        "category": case["category"],
        "split": case["split"],
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
        "answer_reused": rag_reused,
        "baseline_reused": base_reused,
        "answer_key": rag_key,
        "judge_key": rag_score_key,
        "baseline_key": base_key,
        "baseline_judge_key": base_score_key,
    }


async def run(
    settings: Settings,
    kb: KnowledgeBase | None = None,
    concurrency: int = 4,
    saved: dict[str, dict] | None = None,
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
            return await run_case(
                case, settings, kb, graph, baseline_llm, judge_llm, (saved or {}).get(case["id"])
            )

    return await asyncio.gather(*(one(case) for case in cases))


def missing_gold_ids(kb: KnowledgeBase, cases: list[dict]) -> list[str]:
    gold = sorted({g for case in cases for g in case["gold_ids"]})
    found = {c.native_id for c in kb.by_ids(gold)}
    return [g for g in gold if g not in found]


def groups(results: list[dict]) -> dict[str, list[dict]]:
    """Results per category, per split and overall."""
    found: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        found[r["category"]].append(r)
        found[r["split"]].append(r)
    found["all"] = results
    return found


def summarize(results: list[dict]) -> dict[str, dict[str, float | None]]:
    return {
        name: {m: mean([r[m] for r in rows]) for m in METRICS}
        for name, rows in groups(results).items()
    }


def threshold_row(summary: dict[str, dict[str, float | None]]) -> str:
    """Thresholds apply to the holdout; dev stands in until it has questions."""
    return "test" if "test" in summary else "dev"


def check_thresholds(
    summary: dict[str, dict[str, float | None]], thresholds: dict, row: str | None = None
) -> list[str]:
    row = row or threshold_row(summary)
    failures = []
    for metric, minimum in thresholds.items():
        value = summary[row][metric]
        if value is None or value < minimum:
            failures.append(f"{metric}: {value} < {minimum}")
    return failures


def report(results: list[dict], settings: Settings, previous: dict | None = None) -> str:
    """The report; `previous` is the last run in history.jsonl, to list regressions since."""
    summary = summarize(results)
    rows_by_group = groups(results)
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"  # noqa: E731

    def ci(name: str, metric: str) -> str:
        """The mean with its 95% bootstrap interval, e.g. 0.92 [0.85, 0.97]."""
        interval = bootstrap_ci([r[metric] for r in rows_by_group[name]])
        value = fmt(summary[name][metric])
        return value if interval is None else f"{value} [{interval[0]:.2f}, {interval[1]:.2f}]"

    header = (
        "| Category | n | Recall@k | MRR | Correctness (base → RAG) | Citation precision "
        "(base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for name in [*CATEGORIES, *SPLITS, "all"]:
        s = summary.get(name)
        if not s:
            continue
        rows.append(
            f"| {name} | {len(rows_by_group[name])} "
            f"| {ci(name, 'recall_at_10')} | {ci(name, 'mrr')} "
            f"| {fmt(s['baseline_correctness'])} → {ci(name, 'correctness')} "
            f"| {fmt(s['baseline_citation_precision'])} → {ci(name, 'citation_precision')} "
            f"| {fmt(s['baseline_abstention_accuracy'])} → {ci(name, 'abstention_accuracy')} "
            f"| {ci(name, 'faithfulness')} |"
        )
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    failures = check_thresholds(summary, thresholds)
    status = "all thresholds met" if not failures else "FAILED: " + "; ".join(failures)
    row = threshold_row(summary)
    if previous is None:
        changes = "No earlier run in `history.jsonl` to compare with."
    else:
        since = f"Regressions since the run of {previous['date']} ({previous['commit']})"
        found = regressions(previous["scores"], results)
        changes = f"{since}: " + ("none." if not found else "\n\n- " + "\n- ".join(found))
    if row == "dev":
        status += (
            ". No test questions yet: settings were tuned on these dev questions, so they "
            "overstate quality on unseen ones"
        )
    return (
        "# Eval report: AI-security golden set\n\n"
        f"Chat model `{settings.llm_model}` ({settings.llm_provider}); judge "
        f"`{settings.eval_judge_model}` ({settings.eval_judge_provider or settings.llm_provider}) "
        f"with rubric `{RUBRIC.relative_to(ROOT)}`. Baseline: "
        f"{baseline_name(settings)}. {sum(not r['answer_reused'] for r in results)} RAG and "
        f"{sum(not r['baseline_reused'] for r in results)} baseline answers of {len(results)} "
        "were asked anew; the others, and every verdict whose inputs are unchanged, are reused "
        "from earlier runs (`make eval FULL=1` asks everything again, `FRESH=1` the baseline). "
        "Scores are means in [0, 1] with 95% bootstrap "
        "intervals for RAG; judge scores map 1-5 to 0-1. Recall@k counts the first "
        f"{settings.retrieval_top_k} passages, the ones the model sees. Retrieval metrics and "
        "citation precision skip abstention questions. Settings are tuned on `dev`; `test` is "
        "the holdout.\n\n"
        f"Thresholds (`thresholds.yaml`, on the `{row}` row): {status}.\n\n"
        f"{changes}\n\n"
        + header
        + "\n".join(rows)
        + "\n\nPer-question results, answers and judge reasons: `results.json`. "
        f"{sum(c['needs_review'] for c in load_cases())} of {len(results)} questions are "
        "unreviewed drafts (`needs_review: true`) generated from the indexed corpus.\n"
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


class ModelCalled(Exception):
    pass


class Offline:
    """A model or agent that may not be called: `stale_questions` runs the eval with it."""

    def stream(self, messages, *, instructions, max_output_tokens):
        raise ModelCalled

    async def ainvoke(self, *args):
        raise ModelCalled


def load_results() -> dict[str, dict]:
    path = DATASET / "results.json"
    return {r["id"]: r for r in json.loads(path.read_text())} if path.exists() else {}


async def stale_questions(settings: Settings, kb: Retriever | None = None) -> list[str]:
    """IDs of the questions whose saved result `make eval` would change: those it would have to
    ask or judge again (a model or judge input changed, or no result yet), those whose scores the
    current code, retrieval or golden set compute differently, and results without a question."""
    kb = kb or await asyncio.to_thread(open_knowledge_base, settings)
    saved, cases = load_results(), load_cases()
    gate = asyncio.Semaphore(4)
    reuse_flags = {"answer_reused": None, "baseline_reused": None}

    async def stale(case: dict) -> bool:
        if case["id"] not in saved:
            return True
        async with gate:
            try:
                result = await run_case(
                    case, settings, kb, Offline(), Offline(), Offline(), saved[case["id"]]
                )
            except ModelCalled:
                return True
        return result | reuse_flags != saved[case["id"]] | reuse_flags

    flags = await asyncio.gather(*(stale(case) for case in cases))
    asked = {case["id"] for case in cases}
    return [c["id"] for c, f in zip(cases, flags, strict=True) if f] + sorted(set(saved) - asked)


def regressions(before: dict[str, dict], results: list[dict]) -> list[str]:
    """Paired, per-question drops since an earlier run: correctness down 2 points or more on the
    1-5 scale, or an abstention that turned wrong (a refusal turned answer, or the reverse). A
    mean hides them: the test split's correctness interval is about 0.1 wide."""
    found = []
    for r in results:
        if not (old := before.get(r["id"])):
            continue
        if None not in (old["correctness"], r["correctness"]):
            if old["correctness"] - r["correctness"] >= 0.5:
                found.append(
                    f"{r['id']}: correctness {old['correctness']:.2f} → {r['correctness']:.2f}"
                )
        if old["abstention_accuracy"] > r["abstention_accuracy"]:
            found.append(f"{r['id']}: abstention correct → wrong")
    return found


def indexed_versions(client: QdrantClient, collection: str) -> dict[str, str]:
    """Each source's version in a collection: what an eval run searched."""
    found: dict[str, str] = {}
    offset = None
    while True:
        fields = ["source_id", "source_version"]
        records, offset = client.scroll(collection, limit=1024, offset=offset, with_payload=fields)
        found |= {r.payload["source_id"]: r.payload["source_version"] for r in records if r.payload}
        if offset is None:
            return dict(sorted(found.items()))


def last_run() -> dict | None:
    lines = HISTORY.read_text().splitlines() if HISTORY.exists() else []
    return json.loads(lines[-1]) if lines else None


def commit() -> str:
    """The checked-out commit, with `-dirty` if anything is uncommitted."""
    git = ["git", "describe", "--always", "--dirty"]
    found = subprocess.run(git, cwd=ROOT, capture_output=True, text=True)  # noqa: S603 (fixed argv)
    return found.stdout.strip()


async def retrieval_scores(
    kb: Retriever, split: str
) -> tuple[dict[str, dict[str, float | None]], list[float]]:
    """Mean recall@k and MRR per category and `all`, and each retrieval's seconds, sorted."""
    rows = []
    for case in load_cases():
        if not case["gold_ids"] or split not in ("all", case["split"]):
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
        if group := [r for r in rows if name in ("all", r["category"])]:
            summary[name] = {m: mean([r[m] for r in group]) for m in ("recall_at_10", "mrr")}
    return summary, sorted(r["seconds"] for r in rows)


async def retrieval_only(
    settings: Settings, kb: Retriever | None = None, split: str = "dev"
) -> int:
    """Recall@k (k = RETRIEVAL_TOP_K), MRR and retrieval time on one split of the golden set (or
    `all`), with no LLM calls and no files written: a quick loop for tuning retrieval settings on
    dev, confirmed on test."""
    if not any(split in ("all", case["split"]) for case in load_cases()):
        print(f"split {split}: no questions")
        return 1
    kb = kb or await asyncio.to_thread(open_knowledge_base, settings)
    print(f"split: {split}")
    summary, seconds = await retrieval_scores(kb, split)
    for name, scores in summary.items():
        print(f"{name:14} recall@k {scores['recall_at_10']:.3f}  mrr {scores['mrr']:.3f}")
    p50, p95 = seconds[len(seconds) // 2], seconds[int(len(seconds) * 0.95)]
    print(f"retrieval p50 {p50:.2f} s, p95 {p95:.2f} s")
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    failed = check_thresholds(
        summary, {m: thresholds[m] for m in ("recall_at_10", "mrr")}, row="all"
    )
    print(*failed, sep="\n")
    return 1 if failed else 0


async def main(settings: Settings, full: bool = False, fresh_baseline: bool = False) -> int:
    run_commit = commit()  # before this run rewrites the results
    saved = {} if full else load_results()
    if fresh_baseline:
        saved = {i: {**r, "baseline_key": None} for i, r in saved.items()}
    # Pinned: a refresh promoting mid-run doesn't change what the run searches.
    kb = await asyncio.to_thread(open_knowledge_base, settings, True)
    results = await run(settings, kb, saved=saved)
    manifest = corpus_manifest(settings)
    (DATASET / "corpus").mkdir(exist_ok=True)
    (DATASET / "corpus/manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    (DATASET / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    previous = last_run()
    (DATASET / "report.md").write_text(report(results, settings, previous))
    entry = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": run_commit,
        "index": kb.collection,
        "sources": await asyncio.to_thread(indexed_versions, kb.client, kb.collection),
        "answered": sum(not r["answer_reused"] for r in results),
        "summary": summarize(results),
        "scores": {r["id"]: {m: r[m] for m in METRICS} for r in results},
    }
    with HISTORY.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print((DATASET / "report.md").read_text())
    observability.flush()
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())
    return 1 if check_thresholds(summarize(results), thresholds) else 0
