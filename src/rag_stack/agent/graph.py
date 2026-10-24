import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

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

    Streams `{"delta": str}` and `{"usage": int}` as custom events.
    """

    async def retrieve(state: State) -> dict[str, list[dict[str, Any]]]:
        questions = [m["content"] for m in state["messages"] if m["role"] == "user"]
        previous = questions[-2] if len(questions) > 1 else ""
        found = await retriever.retrieve(questions[-1], context=previous)
        return {"sources": [r.chunk.model_dump() for r in found]}

    async def generate(state: State) -> dict[str, list[Message]]:
        write = get_stream_writer()
        language = detect_language(state["messages"][-1]["content"])
        sources = [Chunk.model_validate(s) for s in state["sources"][: settings.retrieval_top_k]]
        if not sources:
            # Nothing relevant was found: abstain without spending tokens.
            text = abstention(await retriever.catalog(), language)
            write({"delta": text})
            return {"messages": [{"role": "assistant", "content": text}]}

        parts: list[str] = []
        # Earlier answers go back without their appended source lists.
        history: list[Message] = [
            {"role": "assistant", "content": m["content"].split(FOOTER_START, 1)[0]}
            if m["role"] == "assistant"
            else m
            for m in build_input(state["messages"], settings.max_history_messages)
        ]
        async for event in llm.stream(
            with_sources(history, sources, settings.max_chunk_chars),
            instructions=SYSTEM_PROMPT,
            max_output_tokens=settings.max_output_tokens,
        ):
            if isinstance(event, TextDelta):
                parts.append(event.text)
                write({"delta": event.text})
            else:
                write({"usage": event.total_tokens})
        answer = "".join(parts)
        if is_abstention(answer):
            tail = abstention(await retriever.catalog(), language).removeprefix(ABSTAIN)
        else:
            tail = footer(answer, sources, language)
        write({"delta": tail})
        return {"messages": [{"role": "assistant", "content": answer + tail}]}

    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile(checkpointer=checkpointer)
