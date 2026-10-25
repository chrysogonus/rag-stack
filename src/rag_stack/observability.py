"""Tracing with self-hosted Langfuse (`make tracing`): the only module that imports its SDK.

Without LANGFUSE_* settings nothing is traced and every function here does nothing, so tests
and untraced runs need no server. A chat turn is one trace: its steps (retrieve, generate) are
observations in it, and a reader's rating is a score on it."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal

from langfuse import Langfuse, propagate_attributes  # noqa: TID251

from rag_stack.config import Settings

_client: Langfuse | None = None
# True inside a traced step, so its stages nest in it instead of each starting a trace.
_traced: ContextVar[bool] = ContextVar("traced", default=False)


class _Untraced:
    def update(self, **_: Any) -> None:
        pass


def configure(settings: Settings) -> None:
    """Trace from now on if Langfuse keys are set. Call once per process, at startup."""
    global _client
    secret = settings.langfuse_secret_key.get_secret_value()
    if settings.langfuse_public_key and secret:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=secret,
            base_url=settings.langfuse_base_url,
        )


def turn_trace_id(thread_id: str, message: int) -> str:
    """The trace of the answer at index `message` of a thread. Derived, not stored, so a rating
    finds its trace from the thread and the answer's position alone."""
    return Langfuse.create_trace_id(seed=f"{thread_id}:{message}")


@contextmanager
def step(
    name: str,
    *,
    as_type: Literal["span", "retriever", "generation"],
    trace_id: str,
    session_id: str | None,
    tags: list[str] | None = None,
    **fields: Any,
) -> Iterator[Any]:
    """One step of a turn as an observation in the turn's trace. Yields something with
    `update(output=..., ...)`; untraced, a stand-in that ignores it."""
    if _client is None:
        yield _Untraced()
        return
    with (
        _client.start_as_current_observation(
            name=name,
            as_type=as_type,  # pyright: ignore[reportArgumentType, reportCallIssue]
            trace_context={"trace_id": trace_id},
            **fields,
        ) as observation,
        propagate_attributes(session_id=session_id, tags=tags),
    ):
        token = _traced.set(True)
        try:
            yield observation
        finally:
            _traced.reset(token)


@contextmanager
def stage(name: str) -> Iterator[None]:
    """A timed part of a traced step (search, rerank); outside one it records nothing."""
    if _client is None or not _traced.get():
        yield
        return
    with _client.start_as_current_observation(name=name, as_type="span"):
        yield


def rate_turn(trace_id: str, helpful: bool) -> bool:
    """Store a reader's rating on a turn's trace; a new rating replaces the old one. False when
    nothing is traced, so the caller can say the rating went nowhere."""
    if _client is None:
        return False
    _client.create_score(
        name="helpful",
        value=1.0 if helpful else 0.0,
        data_type="BOOLEAN",
        trace_id=trace_id,
        score_id=f"{trace_id}-helpful",
    )
    return True


def flush() -> None:
    """Send what is buffered (a CLI run ends before the background exporter's next batch)."""
    if _client is not None:
        _client.flush()
