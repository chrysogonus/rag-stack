from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool


@asynccontextmanager
async def open_checkpointer(database_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    """A Postgres checkpointer over a connection pool, with its tables created."""
    async with AsyncConnectionPool(
        database_url,
        connection_class=AsyncConnection[DictRow],
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        yield checkpointer


async def prune_threads(checkpointer: AsyncPostgresSaver, before: datetime) -> int:
    """Delete the conversations whose last checkpoint was written before `before`."""
    pool = cast(
        AsyncConnectionPool[AsyncConnection[DictRow]], checkpointer.conn
    )  # open_checkpointer's
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT thread_id FROM checkpoints GROUP BY thread_id"
            " HAVING max((checkpoint->>'ts')::timestamptz) < %s",
            (before,),
        )
        threads = [row["thread_id"] for row in await cursor.fetchall()]
    for thread_id in threads:
        await checkpointer.adelete_thread(thread_id)
    return len(threads)
