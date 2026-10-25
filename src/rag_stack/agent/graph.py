import operator
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from rag_stack import observability
from rag_stack.agent.answer import FOOTER_START, abstention, footer, is_abstention
from rag_stack.agent.prompts import ABSTAIN, SYSTEM_PROMPT, build_input, with_sources
from rag_stack.config import Settings
from rag_stack.ingestion.models import Chunk
from rag_stack.llm.base import ChatModel, Message, TextDelta
from rag_stack.retrieval.language import detect_language
from rag_stack.retrieval.retriever import Retriever


class State(TypedDict):
    messages: Annotated[list[Message], operator.add]
    # The ranked chunks retrieved for the latest question (replaced every turn), as plain dicts.
    # The answer uses the first settings.retrieval_top_k; evals score the whole ranking.
    sources: list[dict[str, Any]]


def build_graph(
    llm: ChatModel,
    checkpointer: BaseCheckpointSaver | None,
    settings: Settings,
    retriever: Retriever,
) -> CompiledStateGraph:
    """The knowledge base agent: retrieve chunks for the question, then answer from them.

    Streams `{"delta": str}` and `{"usage": int}` as custom events. A turn is traced as one
    trace, named by the thread and the position of its answer; `tags` in the config label it.
    """

    def traced(name: str, state: State, config: RunnableConfig, **fields: Any):
        turn = config.get("configurable", {})
        thread = turn.get("thread_id")
        return observability.step(
            name,
            # The answer will be the next message: the index the reader's rating refers to.
            trace_id=observability.turn_trace_id(str(thread), len(state["messages"])),
            session_id=thread,
            tags=turn.get("tags"),
            **fields,
        )

    async def retrieve(state: State, config: RunnableConfig) -> dict[str, list[dict[str, Any]]]:
        questions = [m["content"] for m in state["messages"] if m["role"] == "user"]
        previous = questions[-2] if len(questions) > 1 else ""
        with traced("retrieve", state, config, as_type="retriever", input=questions[-1]) as step:
            found = await retriever.retrieve(questions[-1], context=previous)
            step.update(
                output=[
                    {"id": r.chunk.native_id, "via": r.via, "score": round(r.score, 3)}
                    for r in found
                ]
            )
        return {"sources": [r.chunk.model_dump() for r in found]}

    async def generate(state: State, config: RunnableConfig) -> dict[str, list[Message]]:
        with traced(
            "generate", state, config, as_type="generation", model=settings.llm_model
        ) as step:
            reply = await answer(state)
            step.update(input=reply["input"], output=reply["text"], usage_details=reply["usage"])
        return {"messages": [{"role": "assistant", "content": reply["text"]}]}

    async def answer(state: State) -> dict[str, Any]:
        """The answer with its footer, the model input and token usage (none if it abstained
        without asking the model)."""
        write = get_stream_writer()
        language = detect_language(state["messages"][-1]["content"])
        sources = [Chunk.model_validate(s) for s in state["sources"][: settings.retrieval_top_k]]
        if not sources:
            # Nothing relevant was found: abstain without spending tokens.
            text = abstention(await retriever.catalog(), language)
            write({"delta": text})
            return {"text": text, "input": None, "usage": None}

        parts: list[str] = []
        usage = 0
        # Earlier answers go back without their appended source lists.
        history: list[Message] = [
            {"role": "assistant", "content": m["content"].split(FOOTER_START, 1)[0]}
            if m["role"] == "assistant"
            else m
            for m in build_input(state["messages"], settings.max_history_messages)
        ]
        prompt = with_sources(history, sources, settings.max_chunk_chars)
        async for event in llm.stream(
            prompt, instructions=SYSTEM_PROMPT, max_output_tokens=settings.max_output_tokens
        ):
            if isinstance(event, TextDelta):
                parts.append(event.text)
                write({"delta": event.text})
            else:
                usage = event.total_tokens
                write({"usage": usage})
        text = "".join(parts)
        if is_abstention(text):
            tail = abstention(await retriever.catalog(), language).removeprefix(ABSTAIN)
        else:
            tail = footer(text, sources, language)
        write({"delta": tail})
        return {"text": text + tail, "input": prompt, "usage": {"total": usage}}

    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile(checkpointer=checkpointer)
