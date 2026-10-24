# AGENTS.md

## Project

A custom RAG application that powers a chatbot. At its core is the **knowledge base
agent**: it takes a user question, retrieves relevant chunks from the knowledge base, and
writes an answer grounded in them.

## Stack

- Python 3.13, managed with `uv`; tests with `pytest`; lint/format with `ruff`; types with `pyright`
- Qdrant as the vector store (hybrid: dense + BM25 sparse)
- LLM and embedding providers sit behind interfaces in `src/rag_stack/llm/`. All
  provider-specific SDK code lives there, so the rest of the code stays provider-agnostic.
  `LLM_PROVIDER` picks the adapter through `create_chat_model` (`llm/factory.py`): `openai`
  (Responses API), `anthropic` (Messages API) or `openai-compatible` (Chat Completions at
  `LLM_BASE_URL`: Ollama, vLLM, LM Studio, gateways). Use the official `openai` and `anthropic`
  SDKs; ruff bans importing them outside `llm/`, and bans `langchain-openai` everywhere.
- Local development runs on the sub2api gateway (`~/workspace/sub2api`, `codex/gpt-6-luna`),
  which uses a personal ChatGPT subscription. Never deploy with it: production needs an API key.
- Agent orchestration: LangGraph with a custom `StateGraph`. Nodes call our `llm/` interfaces,
  not LangChain chat models.
- API: FastAPI with SSE streaming. Conversations are stored in Postgres (with the LangGraph
  checkpointer).
- Web UI: Vite + React + TypeScript in `web/`
- Tracing: Langfuse. Deploy: Kubernetes (Helm chart in `deploy/`).
- Users are public and anonymous: rate limits, token budgets and input caps are required,
  not optional.

## Layout (planned)

```
src/rag_stack/
  ingestion/   # load, chunk, embed documents into Qdrant
  retrieval/   # query Qdrant, rank and filter chunks
  agent/       # knowledge base agent: LangGraph graph, prompts, guardrails
  llm/         # provider interfaces and adapters
  api/         # FastAPI app: chat (SSE), threads, feedback, rate limits
  db/          # Postgres models and Alembic migrations
web/           # chat UI
deploy/        # Helm chart
tests/
  fakes/       # fake LLM / embedder shared by unit tests
  unit/        # tight: no network, LLM/embeddings faked, Qdrant in-memory
  ai/          # evals against a real LLM, marked @pytest.mark.ai
  e2e/         # question -> chatbot answer, real Qdrant
evals/datasets/<name>/  # corpus/, golden.jsonl, thresholds.yaml used by tests/ai
```

## Commands

`make` lists the shortcuts: `make ci` runs the CI pipeline locally, `make check-all` adds evals
and e2e (the definition of done below), and `make up` / `make down` / `make restart` run the app
in the background (logs in `.run/`). The underlying commands:

```
uv sync
uv run ruff check && uv run ruff format --check && uv run pyright
uv export --frozen --no-emit-project --format requirements-txt > /tmp/req.txt && uvx pip-audit -r /tmp/req.txt --disable-pip
uv run pytest tests/unit
uv run pytest tests/ai     # needs provider API keys in .env
uv run pytest tests/e2e    # needs Postgres + Qdrant (docker compose up -d) and API keys
uv run uvicorn rag_stack.api.app:create_app --factory --reload   # API on :8000

cd web && npm ci
npm run lint && npm test -- --run && npm run build
npm run dev                # chat UI on :5173, proxies /api to :8000
```

## Testing (required)

Every change to RAG or agent code ships with both test layers below:

- **Unit tests**: tight and deterministic. They cover chunking, retrieval logic, prompt
  assembly, and agent control flow, with fakes standing in for the LLM, embeddings, and Qdrant.
- **AI tests (evals)**: these run against a real LLM using golden datasets from `evals/datasets/`.
  They score retrieval (recall/precision) and answers (faithfulness, relevance,
  groundedness) against explicit thresholds, using metrics or an LLM-as-judge.

**E2E tests** cover the full chatbot path, from user question to final answer, against a real
Qdrant instance. Add or extend one whenever a user-visible flow changes.

A change is done when the unit tests pass, every eval meets its threshold, and the e2e suite
is green.

## Conventions

- Secrets stay in `.env`; keep `.env.example` current with every required variable.
- Eval thresholds live next to their dataset. Raise them deliberately and say why in the change.
- Commit messages are concise and on point: a short summary line, plus a brief body only when
  the why isn't obvious. No `Co-Authored-By` or other attribution trailers.
