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
    llm_model: str = "gpt-6-luna"
    database_url: str = "postgresql://rag:rag@127.0.0.1:5432/rag"

    # Users are public and anonymous, so every request is capped.
    max_input_chars: int = 4000
    max_history_messages: int = 20
    # Reasoning tokens count against this, so leave headroom above the visible answer.
    max_output_tokens: int = 4096
    max_turns_per_thread: int = 50
    rate_limit_per_minute: int = 10
    daily_token_budget_per_client: int = 200_000

    eval_judge_model: str = "gpt-6-luna"
    # The chatbot the eval compares RAG answers against. Unset: the RAG model itself without
    # retrieval. Set it to a live general chatbot (e.g. the sub2api gateway) for that reference.
    eval_baseline_provider: Provider | None = None
    eval_baseline_base_url: str | None = None
    eval_baseline_model: str | None = None
    eval_baseline_api_key: SecretStr = SecretStr("")

    # Knowledge base: Qdrant for chunks, open-weights models run locally via fastembed.
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "kb_chunks"
    embedding_model: str = "intfloat/multilingual-e5-large"
    sparse_model: str = "Qdrant/bm25"
    # int8 build of bge-reranker-v2-m3: with rerank_max_chars it reranks 50 candidates in ~7 s
    # on CPU instead of ~45 s, with near-identical rankings (see docs/PLAN.md).
    reranker_model: str = "BAAI/bge-reranker-v2-m3-int8"
    # The reranker reads only the start of each chunk (its cost grows with text length).
    rerank_max_chars: int = 1000
    retrieval_candidates: int = 50
    retrieval_top_k: int = 8
    # Reranker logit below which a hybrid hit counts as irrelevant (exact-ID hits always pass).
    # Calibrated on the golden set: off-topic questions top out near -1, answerable ones above 1.
    rerank_min_score: float = 0.0
    max_chunk_chars: int = 2500

    # Ingestion
    data_dir: str = "data"
    fetch_user_agent: str = "rag-stack/0.1 (AI-security knowledge base ingest)"
    fetch_cache_ttl_hours: float = 24
    nvd_api_key: SecretStr = SecretStr("")
