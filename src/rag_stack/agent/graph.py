import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from rag_stack.agent.prompts import SYSTEM_PROMPT, build_input
from rag_stack.config import Settings
from rag_stack.llm.base import ChatModel, Message, TextDelta


class State(TypedDict):
    messages: Annotated[list[Message], operator.add]


def build_graph(
    llm: ChatModel, checkpointer: BaseCheckpointSaver | None, settings: Settings
) -> CompiledStateGraph:
    """The knowledge base agent. For now it answers with a single LLM call, no retrieval.

    Streams `{"delta": str}` and a final `{"usage": int}` as custom events.
    """

    async def generate(state: State) -> dict[str, list[Message]]:
        write = get_stream_writer()
        parts: list[str] = []
        async for event in llm.stream(
            build_input(state["messages"], settings.max_history_messages),
            instructions=SYSTEM_PROMPT,
            max_output_tokens=settings.max_output_tokens,
        ):
            if isinstance(event, TextDelta):
                parts.append(event.text)
                write({"delta": event.text})
            else:
                write({"usage": event.total_tokens})
        return {"messages": [{"role": "assistant", "content": "".join(parts)}]}

    graph = StateGraph(State)
    graph.add_node("generate", generate)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", END)
    return graph.compile(checkpointer=checkpointer)
