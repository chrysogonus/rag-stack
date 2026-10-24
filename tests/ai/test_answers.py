import asyncio
import json
import re
from pathlib import Path

import pytest
import yaml
from langgraph.checkpoint.memory import InMemorySaver

from rag_stack.agent.graph import build_graph
from rag_stack.config import Settings
from rag_stack.llm.base import ChatModel, Message, TextDelta
from rag_stack.llm.factory import create_chat_model

pytestmark = [pytest.mark.ai, pytest.mark.anyio]

DATASET = Path(__file__).parents[2] / "evals/datasets/general_qa"

JUDGE_PROMPT = """\
You grade a chatbot's answer to the user's last question. Score each criterion from 1 to 5:

- relevance: does the answer address the question, using the conversation for context?
  5 = fully on point, 1 = off topic.
- correctness: does the answer state the key facts, without contradicting them or adding false
  claims? 5 = all key facts, nothing wrong; 1 = wrong or missing.

Reply with JSON only: {"relevance": <1-5>, "correctness": <1-5>, "reason": "<one sentence>"}"""


async def complete(llm: ChatModel, messages: list[Message], instructions: str) -> str:
    parts = [
        event.text
        async for event in llm.stream(messages, instructions=instructions, max_output_tokens=2048)
        if isinstance(event, TextDelta)
    ]
    return "".join(parts)


async def run_case(case: dict, graph, judge: ChatModel) -> dict:
    history: list[Message] = case.get("history", [])
    question: Message = {"role": "user", "content": case["question"]}
    result = await graph.ainvoke(
        {"messages": [*history, question]}, {"configurable": {"thread_id": case["id"]}}
    )
    answer = result["messages"][-1]["content"]

    grading = json.dumps(
        {
            "conversation": history,
            "question": case["question"],
            "key_facts": case["key_facts"],
            "answer": answer,
        },
        ensure_ascii=False,
    )
    reply = await complete(judge, [{"role": "user", "content": grading}], JUDGE_PROMPT)
    # Take the first {...} block: some models wrap the JSON in prose or a code fence.
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    assert match, f"{case['id']}: judge returned no JSON: {reply!r}"
    verdict = json.loads(match.group())
    return {
        "id": case["id"],
        "answer": answer,
        "relevance": (verdict["relevance"] - 1) / 4,
        "correctness": (verdict["correctness"] - 1) / 4,
        "reason": verdict["reason"],
    }


async def test_answers_meet_thresholds():
    settings = Settings()
    api_key = settings.llm_api_key.get_secret_value()
    if settings.llm_provider != "openai-compatible" and not api_key:
        pytest.fail(f"LLM_API_KEY is not set; {settings.llm_provider} needs one in .env.")

    def model(name: str) -> ChatModel:
        return create_chat_model(
            settings.llm_provider, name, api_key=api_key, base_url=settings.llm_base_url
        )

    graph = build_graph(model(settings.llm_model), InMemorySaver(), settings)
    judge = model(settings.eval_judge_model)
    cases = [json.loads(line) for line in (DATASET / "golden.jsonl").read_text().splitlines()]
    thresholds = yaml.safe_load((DATASET / "thresholds.yaml").read_text())

    results = await asyncio.gather(*(run_case(case, graph, judge) for case in cases))

    report = "\n".join(
        f"{r['id']}: relevance={r['relevance']:.2f} correctness={r['correctness']:.2f} "
        f"({r['reason']})"
        for r in results
    )
    print(report)
    for metric, threshold in thresholds.items():
        mean = sum(r[metric] for r in results) / len(results)
        assert mean >= threshold, f"{metric} {mean:.2f} < {threshold}\n{report}"
