from typing import Literal

from anthropic import AsyncAnthropic  # noqa: TID251
from openai import AsyncOpenAI  # noqa: TID251

from rag_stack.llm.anthropic_messages import AnthropicModel
from rag_stack.llm.base import ChatModel
from rag_stack.llm.embeddings import Embedder, Reranker, SparseEmbedder
from rag_stack.llm.openai_compatible import OpenAICompatibleModel
from rag_stack.llm.openai_responses import OpenAIResponsesModel

Provider = Literal["openai", "openai-compatible", "anthropic"]
# Where an embedding or reranking model runs: in-process on the CPU, or on a vLLM server.
ModelHost = Literal["fastembed", "vllm"]


def create_chat_model(
    provider: Provider, model: str, *, api_key: str, base_url: str | None = None
) -> ChatModel:
    """Build the chat model for a provider. The only place that constructs SDK clients."""
    base_url = base_url or None  # an empty LLM_BASE_URL= means the provider's default
    if provider == "openai":
        return OpenAIResponsesModel(AsyncOpenAI(api_key=api_key, base_url=base_url), model)
    if provider == "openai-compatible":
        if not base_url:
            # Without it the SDK would quietly send every question to api.openai.com.
            raise ValueError("LLM_PROVIDER=openai-compatible needs LLM_BASE_URL")
        # Local servers usually need no key, but the SDK refuses to start without one.
        client = AsyncOpenAI(api_key=api_key or "not-needed", base_url=base_url)
        return OpenAICompatibleModel(client, model)
    return AnthropicModel(AsyncAnthropic(api_key=api_key, base_url=base_url), model)


def create_embedder(
    model: str, provider: ModelHost = "fastembed", base_url: str | None = None
) -> Embedder:
    if provider == "vllm":
        from openai import OpenAI  # noqa: TID251

        from rag_stack.llm.vllm_models import VllmDense

        return VllmDense(OpenAI(api_key="not-needed", base_url=served_at(base_url)), model)
    from rag_stack.llm.fastembed_local import FastembedDense

    return FastembedDense(model)


def create_sparse_embedder(model: str) -> SparseEmbedder:
    from rag_stack.llm.fastembed_local import FastembedSparse

    return FastembedSparse(model)


def create_reranker(
    model: str, provider: ModelHost = "fastembed", base_url: str | None = None
) -> Reranker:
    if provider == "vllm":
        import httpx

        from rag_stack.llm.vllm_models import VllmReranker

        return VllmReranker(httpx.Client(base_url=served_at(base_url), timeout=60), model)
    from rag_stack.llm.fastembed_local import FastembedReranker

    return FastembedReranker(model)


def served_at(base_url: str | None) -> str:
    if not base_url:
        raise ValueError("a vLLM-served model needs its base URL, e.g. http://127.0.0.1:8001/v1")
    return base_url.rstrip("/") + "/"
