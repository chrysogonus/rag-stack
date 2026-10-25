import pytest
from fakes.embeddings import FakeRetriever, chunk
from fakes.llm import FakeChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from rag_stack.agent.graph import build_graph
from rag_stack.agent.prompts import ABSTAIN, SYSTEM_PROMPT
from rag_stack.config import Settings

pytestmark = pytest.mark.anyio

T0051 = chunk("AML.T0051", "LLM Prompt Injection (technique)\n\nAn adversary may craft prompts.")


def config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


async def ask(graph, thread_id: str, question: str) -> list:
    parts = graph.astream(
        {"messages": [{"role": "user", "content": question}]},
        config(thread_id),
        stream_mode="custom",
    )
    return [part async for part in parts]


async def test_answers_from_retrieved_sources_and_appends_the_footer():
    llm = FakeChatModel("It is [AML.T0051](https://example.org/AML.T0051).", tokens_per_reply=42)
    graph = build_graph(llm, InMemorySaver(), Settings(max_output_tokens=123), FakeRetriever(T0051))

    events = await ask(graph, "t1", "What is AML.T0051?")

    deltas = "".join(e["delta"] for e in events if "delta" in e)
    assert {"usage": 42} in events
    assert deltas.startswith("It is [AML.T0051](https://example.org/AML.T0051).")
    assert "**Sources**" in deltas
    assert "Copyright 2021-2026 MITRE" in deltas
    assert "Source versions: MITRE ATLAS 2026.09" in deltas
    assert "AI-generated answer (EU AI Act Art. 50(1))" in deltas
    state = await graph.aget_state(config("t1"))
    assert state.values["messages"][-1] == {"role": "assistant", "content": deltas}
    call = llm.calls[0]
    assert call["instructions"] == SYSTEM_PROMPT
    assert call["max_output_tokens"] == 123
    prompt = call["messages"][-1]["content"]
    assert '<source n="1" id="AML.T0051" url="https://example.org/AML.T0051"' in prompt
    assert prompt.endswith("Question: What is AML.T0051?")


async def test_no_relevant_sources_abstains_without_calling_the_llm():
    llm = FakeChatModel()
    retriever = FakeRetriever(catalog=["MITRE ATLAS", "KI-MIG"])
    graph = build_graph(llm, InMemorySaver(), Settings(), retriever)

    events = await ask(graph, "t1", "What is the capital of France?")

    text = "".join(e["delta"] for e in events)
    assert text.startswith(ABSTAIN)
    assert "- MITRE ATLAS\n- KI-MIG" in text
    assert llm.calls == []
    assert not any("usage" in e for e in events)


async def test_an_abstaining_llm_gets_the_list_of_indexed_sources():
    graph = build_graph(FakeChatModel(ABSTAIN), InMemorySaver(), Settings(), FakeRetriever(T0051))

    events = await ask(graph, "t1", "Welche Farbe hat der Himmel?")

    text = "".join(e.get("delta", "") for e in events)
    assert text.startswith(ABSTAIN + "\n\nNennen Sie am besten")
    assert "Die Wissensbasis umfasst:" in text
    assert "**Quellen**" not in text


async def test_follow_up_passes_the_previous_question_and_strips_old_footers():
    llm = FakeChatModel("First [AML.T0051].", "Second.")
    retriever = FakeRetriever(T0051)
    graph = build_graph(llm, InMemorySaver(), Settings(), retriever)

    await ask(graph, "t1", "What is AML.T0051?")
    await ask(graph, "t1", "How is it mitigated?")

    assert retriever.calls[1] == ("How is it mitigated?", "What is AML.T0051?")
    history = llm.calls[1]["messages"]
    assert history[0] == {"role": "user", "content": "What is AML.T0051?"}
    assert history[1] == {"role": "assistant", "content": "First [AML.T0051]."}


async def test_user_markdown_that_looks_like_a_footer_is_kept():
    llm = FakeChatModel("Answer.")
    graph = build_graph(llm, InMemorySaver(), Settings(), FakeRetriever(T0051))
    question = "Please answer the following:\n\n---\n**Question**: What is AML.T0051?"

    await ask(graph, "t1", question)

    assert llm.calls[0]["messages"][-1]["content"].endswith(f"Question: {question}")


async def test_history_sent_to_the_llm_is_capped():
    llm = FakeChatModel()
    graph = build_graph(
        llm, InMemorySaver(), Settings(max_history_messages=3), FakeRetriever(T0051)
    )

    for i in range(4):
        await ask(graph, "t1", f"q{i}")

    assert [m["role"] for m in llm.calls[-1]["messages"]] == ["user", "assistant", "user"]
    assert llm.calls[-1]["messages"][0]["content"] == "q2"


async def test_threads_are_isolated():
    llm = FakeChatModel("one", "two")
    graph = build_graph(llm, InMemorySaver(), Settings(), FakeRetriever(T0051))

    await ask(graph, "t1", "first thread")
    await ask(graph, "t2", "second thread")

    assert len(llm.calls[1]["messages"]) == 1
