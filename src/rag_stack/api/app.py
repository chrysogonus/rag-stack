import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, StringConstraints

from rag_stack.agent.graph import build_graph
from rag_stack.api.limits import ClientLimiter
from rag_stack.config import Settings
from rag_stack.db.checkpointer import open_checkpointer
from rag_stack.llm.base import ChatModel, Message
from rag_stack.llm.factory import create_chat_model

logger = logging.getLogger(__name__)


def get_graph(request: Request) -> CompiledStateGraph:
    return request.app.state.graph


Graph = Annotated[CompiledStateGraph, Depends(get_graph)]


def create_app(
    settings: Settings | None = None,
    llm: ChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> FastAPI:
    """Build the API. `llm` and `checkpointer` default to OpenAI and Postgres."""
    settings = settings or Settings()
    limiter = ClientLimiter(settings.rate_limit_per_minute, settings.daily_token_budget_per_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            saver = checkpointer or await stack.enter_async_context(
                open_checkpointer(settings.database_url)
            )
            model = llm or create_chat_model(
                settings.llm_provider,
                settings.llm_model,
                api_key=settings.llm_api_key.get_secret_value(),
                base_url=settings.llm_base_url,
            )
            app.state.graph = build_graph(model, saver, settings)
            yield

    app = FastAPI(title="rag-stack", lifespan=lifespan)

    class NewMessage(BaseModel):
        content: Annotated[
            str,
            StringConstraints(
                strip_whitespace=True, min_length=1, max_length=settings.max_input_chars
            ),
        ]

    def thread_config(thread_id: UUID) -> RunnableConfig:
        return {"configurable": {"thread_id": str(thread_id)}}

    async def admit(thread_id: UUID, body: NewMessage, request: Request, graph: Graph) -> str:
        """Refuse the turn before streaming starts, so the client gets a real status code."""
        state = await graph.aget_state(thread_config(thread_id))
        messages: list[Message] = state.values.get("messages", [])
        if sum(m["role"] == "user" for m in messages) >= settings.max_turns_per_thread:
            raise HTTPException(409, "This conversation is full. Please start a new chat.")
        client = request.client.host if request.client else "unknown"
        if refusal := limiter.check(client):
            raise HTTPException(429, refusal)
        return client

    @app.get("/api/threads/{thread_id}/messages")
    async def get_messages(thread_id: UUID, graph: Graph) -> list[Message]:
        state = await graph.aget_state(thread_config(thread_id))
        return state.values.get("messages", [])

    @app.post("/api/threads/{thread_id}/messages", response_class=EventSourceResponse)
    async def post_message(
        thread_id: UUID,
        body: NewMessage,
        client: Annotated[str, Depends(admit)],
        graph: Graph,
    ) -> AsyncIterator[ServerSentEvent]:
        user: Message = {"role": "user", "content": body.content}
        try:
            async for part in graph.astream(
                {"messages": [user]},
                thread_config(thread_id),
                stream_mode=["custom", "updates"],
                version="v2",
            ):
                if part["type"] == "custom":
                    if "delta" in part["data"]:
                        yield ServerSentEvent(event="delta", data={"text": part["data"]["delta"]})
                    else:
                        limiter.charge(client, part["data"]["usage"])
                elif part["type"] == "updates" and "generate" in part["data"]:
                    reply = part["data"]["generate"]["messages"][-1]
                    yield ServerSentEvent(event="done", data={"message": reply})
        except Exception:
            logger.exception("Chat turn failed for thread %s", thread_id)
            yield ServerSentEvent(
                event="error", data={"detail": "Something went wrong. Please try again."}
            )

    return app
