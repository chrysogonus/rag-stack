import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fakes.embeddings import FakeRetriever, chunk
from fakes.llm import FakeChatModel
from langfuse import Langfuse  # noqa: TID251
from langgraph.checkpoint.memory import InMemorySaver
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from rag_stack import observability
from rag_stack.agent.graph import build_graph
from rag_stack.config import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def spans(monkeypatch) -> Iterator[InMemorySpanExporter]:
    """Tracing on, into memory instead of a Langfuse server."""
    exporter = InMemorySpanExporter()
    client = Langfuse(
        # The SDK keeps one exporter per public key: a fresh key gets this test's.
        public_key=f"pk-test-{uuid.uuid4()}",
        secret_key="sk-test",  # noqa: S106 (no server is contacted)
        base_url="http://127.0.0.1:9",
        span_exporter=exporter,
        tracer_provider=TracerProvider(),
    )
    monkeypatch.setattr(observability, "_client", client)
    yield exporter
    client.shutdown()


async def test_untraced_steps_and_ratings_do_nothing(monkeypatch):
    monkeypatch.setattr(observability, "_client", None)

    with observability.step(
        "retrieve", as_type="retriever", trace_id="0" * 32, session_id="t"
    ) as s:
        s.update(output="ignored")
        with observability.stage("rerank"):
            pass
    assert observability.rate_turn("0" * 32, True) is False


def test_configure_traces_only_with_keys(monkeypatch):
    monkeypatch.setattr(observability, "_client", None)

    observability.configure(Settings())
    assert observability._client is None


def test_a_turn_trace_is_named_by_thread_and_answer_position():
    assert observability.turn_trace_id("t", 1) == observability.turn_trace_id("t", 1)
    assert observability.turn_trace_id("t", 1) != observability.turn_trace_id("t", 3)
    assert len(observability.turn_trace_id("t", 1)) == 32


async def test_a_chat_turn_is_one_trace_with_its_steps(spans):
    graph = build_graph(
        FakeChatModel("It is prompt injection [AML.T0051]."),
        InMemorySaver(),
        Settings(),
        FakeRetriever(chunk("AML.T0051")),
    )

    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "What is AML.T0051?"}]},
        {"configurable": {"thread_id": "t1", "tags": ["eval"]}},
    )
    observability.flush()

    found = {s.name: s for s in spans.get_finished_spans()}
    assert set(found) == {"retrieve", "generate"}
    # The answer is message 1 of the thread: the index a rating of it names.
    trace = observability.turn_trace_id("t1", 1)
    assert {format(s.context.trace_id, "032x") for s in found.values()} == {trace}
    generate = found["generate"].attributes or {}
    assert generate["langfuse.observation.model.name"] == Settings().llm_model
    assert "AML.T0051" in str(generate["langfuse.observation.output"])
    assert (found["retrieve"].attributes or {})["session.id"] == "t1"


async def test_stages_nest_in_their_step_even_in_a_worker_thread(spans):
    def rerank() -> None:
        with observability.stage("rerank"):
            pass

    trace = observability.turn_trace_id("t", 1)
    with observability.step("retrieve", as_type="retriever", trace_id=trace, session_id="t"):
        await asyncio.to_thread(rerank)
    rerank()  # outside a step: not recorded
    observability.flush()

    found = {s.name: s for s in spans.get_finished_spans()}
    assert set(found) == {"retrieve", "rerank"}
    parent = found["rerank"].parent
    assert parent is not None and parent.span_id == found["retrieve"].context.span_id


def test_a_rating_is_one_score_per_answer(monkeypatch):
    class Recorder:
        def __init__(self) -> None:
            self.scores: list[dict] = []

        def create_score(self, **score) -> None:
            self.scores.append(score)

    recorder = Recorder()
    monkeypatch.setattr(observability, "_client", recorder)

    assert observability.rate_turn("a" * 32, True) is True
    observability.rate_turn("a" * 32, False)

    assert [s["value"] for s in recorder.scores] == [1.0, 0.0]
    # The same score id: a new rating replaces the old one.
    assert {s["score_id"] for s in recorder.scores} == {f"{'a' * 32}-helpful"}
    assert recorder.scores[0]["data_type"] == "BOOLEAN"
