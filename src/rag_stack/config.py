from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_stack.llm.factory import ModelHost, Provider


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
    # Where the judge runs. Unset: on the RAG model's provider (LLM_*).
    eval_judge_provider: Provider | None = None
    eval_judge_base_url: str | None = None
    eval_judge_api_key: SecretStr = SecretStr("")
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
    # int8 build of bge-reranker-v2-m3: near-identical rankings to the full model at a fraction
    # of the CPU time (see docs/PLAN.md). The reranker is nearly all of retrieval's latency.
    reranker_model: str = "BAAI/bge-reranker-v2-m3-int8"
    # `vllm`: the models run on the GPU services of `docker compose --profile gpu`, at these
    # OpenAI-compatible base URLs (e.g. http://127.0.0.1:8001/v1).
    embedding_provider: ModelHost = "fastembed"
    embedding_base_url: str | None = None
    reranker_provider: ModelHost = "fastembed"
    reranker_base_url: str | None = None

    @property
    def embedding(self) -> str:
        """The configured embedding model as its vectors record it (`Embedder.name`)."""
        return f"{self.embedding_provider}:{self.embedding_model}"

    # The reranker reads only the start of each chunk (its cost grows with text length).
    # 20 candidates x 800 chars: retrieval p50 2.6 s / p95 4.1 s on CPU (was 7.9 / 11.2 s at
    # 50 x 1000) with the same golden-set recall@10 (0.962) and MRR (0.906 vs 0.900); 600 chars
    # loses a CVE question (`eval --retrieval-only` to re-check).
    rerank_max_chars: int = 800
    retrieval_candidates: int = 20
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

    # Tracing: the self-hosted Langfuse from `make tracing`. Without keys nothing is traced.
    langfuse_base_url: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
