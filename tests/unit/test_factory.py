import pytest
from pydantic import ValidationError

from rag_stack.config import Settings
from rag_stack.llm.anthropic_messages import AnthropicModel
from rag_stack.llm.factory import create_chat_model
from rag_stack.llm.openai_compatible import OpenAICompatibleModel
from rag_stack.llm.openai_responses import OpenAIResponsesModel


def test_openai_uses_the_responses_api():
    model = create_chat_model("openai", "gpt-6-astra", api_key="sk-test")

    assert isinstance(model, OpenAIResponsesModel)
    assert model._model == "gpt-6-astra"
    assert model._client.api_key == "sk-test"
    assert str(model._client.base_url) == "https://api.openai.com/v1/"


@pytest.mark.parametrize("base_url", [None, ""])
def test_hosted_providers_use_their_default_url_when_none_is_set(base_url):
    openai = create_chat_model("openai", "gpt-6-astra", api_key="k", base_url=base_url)
    anthropic = create_chat_model("anthropic", "claude-sonnet-5-5", api_key="k", base_url=base_url)

    assert isinstance(openai, OpenAIResponsesModel)
    assert isinstance(anthropic, AnthropicModel)
    assert str(openai._client.base_url) == "https://api.openai.com/v1/"
    assert str(anthropic._client.base_url) == "https://api.anthropic.com"


def test_openai_compatible_talks_to_the_base_url():
    model = create_chat_model(
        "openai-compatible",
        "codex/gpt-6-luna",
        api_key="secret",
        base_url="http://127.0.0.1:11435/v1",
    )

    assert isinstance(model, OpenAICompatibleModel)
    assert model._model == "codex/gpt-6-luna"
    assert model._client.api_key == "secret"
    assert str(model._client.base_url) == "http://127.0.0.1:11435/v1/"


def test_openai_compatible_without_a_key_gets_a_placeholder():
    model = create_chat_model(
        "openai-compatible", "llama3.3", api_key="", base_url="http://127.0.0.1:11434/v1"
    )

    assert isinstance(model, OpenAICompatibleModel)
    assert model._client.api_key == "not-needed"


def test_openai_compatible_requires_a_base_url():
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        create_chat_model("openai-compatible", "llama3.3", api_key="")


def test_anthropic_uses_the_messages_api():
    model = create_chat_model("anthropic", "claude-sonnet-5-5", api_key="sk-ant-test")

    assert isinstance(model, AnthropicModel)
    assert model._model == "claude-sonnet-5-5"
    assert model._client.api_key == "sk-ant-test"


def test_settings_reject_unknown_providers():
    with pytest.raises(ValidationError):
        Settings(llm_provider="gemini")  # pyright: ignore[reportArgumentType]
