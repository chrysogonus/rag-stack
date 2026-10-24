from typing import Literal

from anthropic import AsyncAnthropic  # noqa: TID251
from openai import AsyncOpenAI  # noqa: TID251

from rag_stack.llm.anthropic_messages import AnthropicModel
from rag_stack.llm.base import ChatModel
from rag_stack.llm.openai_compatible import OpenAICompatibleModel
from rag_stack.llm.openai_responses import OpenAIResponsesModel

Provider = Literal["openai", "openai-compatible", "anthropic"]


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
