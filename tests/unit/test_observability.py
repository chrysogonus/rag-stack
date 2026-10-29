import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace

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
    assert await observability.rate_turn("0" * 32, True) is False


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


class Scores:
    """Stands in for the Langfuse scores API: records what is sent, answers with `result`."""

    def __init__(self, result: object = None) -> None:
        self.sent: list = []
        self.result = result
        self.scores = self

    async def create(self, *, request, request_options=None) -> object:
        self.sent.extend(request)
        return self.result


async def test_a_rating_is_one_score_per_answer(monkeypatch):
    api = Scores()
    monkeypatch.setattr(observability, "_client", SimpleNamespace(async_api=api))

    assert await observability.rate_turn("a" * 32, True) is True
    await observability.rate_turn("a" * 32, False)

    assert [s.value for s in api.sent] == [1.0, 0.0]
    # The same score id: a new rating replaces the old one.
    assert {s.id for s in api.sent} == {f"{'a' * 32}-helpful"}
    assert {s.trace_id for s in api.sent} == {"a" * 32}
    assert api.sent[0].data_type == "BOOLEAN"


async def test_a_rating_langfuse_rejects_is_not_stored(monkeypatch):
    rejected = SimpleNamespace(accepted=0, rejected=1, errors=[])
    monkeypatch.setattr(observability, "_client", SimpleNamespace(async_api=Scores(rejected)))

    assert await observability.rate_turn("a" * 32, True) is False


async def test_a_rating_is_not_stored_while_langfuse_is_unreachable(spans):
    # The fixture's client points at a closed port: the rating must fail, not vanish in a queue.
    assert await observability.rate_turn("a" * 32, True) is False


class Traces:
    """Langfuse's observation list (two pages) and trace deletion."""

    def __init__(self) -> None:
        self.asked: list[dict] = []
        self.deleted: list[list[str]] = []
        self.observations = SimpleNamespace(get_many=self._get_many)
        self.trace = SimpleNamespace(delete_multiple=self._delete_multiple)

    async def _get_many(self, **query):
        self.asked.append(query)
        if query["cursor"] is None:
            data = [SimpleNamespace(trace_id="t1"), SimpleNamespace(trace_id="t2")]
            return SimpleNamespace(data=data, meta=SimpleNamespace(cursor="next"))
        data = [SimpleNamespace(trace_id="t2"), SimpleNamespace(trace_id=None)]
        return SimpleNamespace(data=data, meta=SimpleNamespace(cursor=None))

    async def _delete_multiple(self, trace_ids):
        self.deleted.append(trace_ids)


async def test_prune_deletes_each_trace_started_before_the_cutoff_once(monkeypatch):
    api = Traces()
    monkeypatch.setattr(observability, "_client", SimpleNamespace(async_api=api))
    cutoff = datetime(2026, 10, 1, tzinfo=UTC)

    assert await observability.prune_traces(cutoff) == 2
    assert {q["to_start_time"] for q in api.asked} == {cutoff}
    assert api.deleted == [["t1", "t2"]]


async def test_prune_without_tracing_does_nothing(monkeypatch):
    monkeypatch.setattr(observability, "_client", None)

    assert await observability.prune_traces(datetime.now(UTC)) is None
