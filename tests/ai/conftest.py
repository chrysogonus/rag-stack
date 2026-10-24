import pytest

from rag_stack.config import Settings
from rag_stack.llm.base import ChatModel
from rag_stack.llm.factory import create_chat_model


@pytest.fixture(scope="session")
def settings() -> Settings:
    settings = Settings()
    if settings.llm_provider != "openai-compatible" and not settings.llm_api_key.get_secret_value():
        pytest.fail(f"LLM_API_KEY is not set; {settings.llm_provider} needs one in .env.")
    return settings


@pytest.fixture(scope="session")
def llm(settings: Settings) -> ChatModel:
    return create_chat_model(
        settings.llm_provider,
        settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
    )
