import pytest
from fakes.llm import FakeChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from rag_stack.agent.graph import build_graph
from rag_stack.agent.prompts import SYSTEM_PROMPT
from rag_stack.config import Settings

pytestmark = pytest.mark.anyio


def config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


async def ask(graph, thread_id: str, question: str) -> list:
    parts = graph.astream(
        {"messages": [{"role": "user", "content": question}]},
        config(thread_id),
        stream_mode="custom",
    )
    return [part async for part in parts]


async def test_streams_deltas_and_usage_and_stores_both_messages():
    llm = FakeChatModel("Paris is the capital.", tokens_per_reply=42)
    graph = build_graph(llm, InMemorySaver(), Settings(max_output_tokens=123))

    events = await ask(graph, "t1", "Capital of France?")

    assert events == [
        {"delta": "Paris"},
        {"delta": " is"},
        {"delta": " the"},
        {"delta": " capital."},
        {"usage": 42},
    ]
    state = await graph.aget_state(config("t1"))
    assert state.values["messages"] == [
        {"role": "user", "content": "Capital of France?"},
        {"role": "assistant", "content": "Paris is the capital."},
    ]
    assert llm.calls[0]["instructions"] == SYSTEM_PROMPT
    assert llm.calls[0]["max_output_tokens"] == 123


async def test_follow_up_sends_earlier_turns_to_the_llm():
    llm = FakeChatModel("Paris.", "About 2 million.")
    graph = build_graph(llm, InMemorySaver(), Settings())

    await ask(graph, "t1", "Capital of France?")
    await ask(graph, "t1", "How many people live there?")

    assert llm.calls[1]["messages"] == [
        {"role": "user", "content": "Capital of France?"},
        {"role": "assistant", "content": "Paris."},
        {"role": "user", "content": "How many people live there?"},
    ]


async def test_history_sent_to_the_llm_is_capped():
    llm = FakeChatModel()
    graph = build_graph(llm, InMemorySaver(), Settings(max_history_messages=3))

    for i in range(4):
        await ask(graph, "t1", f"q{i}")

    assert [m["content"] for m in llm.calls[-1]["messages"]] == ["q2", "ok", "q3"]


async def test_threads_are_isolated():
    llm = FakeChatModel("one", "two")
    graph = build_graph(llm, InMemorySaver(), Settings())

    await ask(graph, "t1", "first thread")
    await ask(graph, "t2", "second thread")

    assert llm.calls[1]["messages"] == [{"role": "user", "content": "second thread"}]
