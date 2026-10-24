from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_stack.llm.factory import Provider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # openai: OpenAI's API. anthropic: Anthropic's API. openai-compatible: any Chat Completions
    # server at llm_base_url (Ollama, vLLM, LM Studio, gateways such as sub2api).
    llm_provider: Provider = "openai"
    llm_base_url: str | None = None
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-6-astra"
    database_url: str = "postgresql://rag:rag@127.0.0.1:5432/rag"

    # Users are public and anonymous, so every request is capped.
    max_input_chars: int = 4000
    max_history_messages: int = 20
    # Reasoning tokens count against this, so leave headroom above the visible answer.
    max_output_tokens: int = 4096
    max_turns_per_thread: int = 50
    rate_limit_per_minute: int = 10
    daily_token_budget_per_client: int = 200_000

    eval_judge_model: str = "gpt-6-astra"
