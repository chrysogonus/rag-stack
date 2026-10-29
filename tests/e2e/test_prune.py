"""Deleting old conversations, against the real Postgres checkpointer."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import empty_checkpoint

from rag_stack.config import Settings
from rag_stack.db.checkpointer import open_checkpointer, prune_threads

pytestmark = [pytest.mark.e2e, pytest.mark.anyio]


async def test_prune_deletes_only_conversations_last_written_before_the_cutoff():
    # A cutoff long before any real conversation: the database may hold a developer's chats.
    cutoff = datetime(2000, 1, 2, tzinfo=UTC)
    old, recent = str(uuid.uuid4()), str(uuid.uuid4())
    async with open_checkpointer(Settings().database_url) as checkpointer:
        for thread_id, written in [
            (old, cutoff - timedelta(days=1)),
            (recent, cutoff + timedelta(days=1)),
        ]:
            checkpoint = empty_checkpoint()
            checkpoint["ts"] = written.isoformat()
            config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            await checkpointer.aput(config, checkpoint, {}, {})

        try:
            assert await prune_threads(checkpointer, cutoff) == 1
            assert await checkpointer.aget_tuple({"configurable": {"thread_id": old}}) is None
            assert await checkpointer.aget_tuple({"configurable": {"thread_id": recent}})
        finally:
            await checkpointer.adelete_thread(old)
            await checkpointer.adelete_thread(recent)
