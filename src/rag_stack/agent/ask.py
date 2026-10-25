import uuid

from langgraph.checkpoint.memory import InMemorySaver

from rag_stack import observability
from rag_stack.agent.graph import build_graph
from rag_stack.config import Settings
from rag_stack.llm.factory import create_chat_model
from rag_stack.retrieval.retriever import open_knowledge_base


async def ask(settings: Settings, question: str) -> int:
    """Answer one question on stdout, streaming like the chat UI does."""
    llm = create_chat_model(
        settings.llm_provider,
        settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
    )
    graph = build_graph(llm, InMemorySaver(), settings, open_knowledge_base(settings))
    async for event in graph.astream(
        {"messages": [{"role": "user", "content": question}]},
        {"configurable": {"thread_id": str(uuid.uuid4())}},
        stream_mode="custom",
    ):
        if "delta" in event:
            print(event["delta"], end="", flush=True)
    print()
    observability.flush()
    return 0
