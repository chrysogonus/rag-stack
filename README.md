# rag-stack

A custom retrieval-augmented generation (RAG) application that powers a chatbot. At its core is
a knowledge base agent that answers user questions from your documents.

**How it works:** documents are ingested, chunked, and embedded into Qdrant. For each question,
the agent retrieves the most relevant chunks and writes an answer grounded in them. The LLM and
embedding providers are pluggable.

> Status: first slice. The chat UI streams answers from the knowledge base agent, and
> conversations persist in Postgres. The agent does not retrieve yet: it answers with a single
> LLM call. The provider is configurable (OpenAI, Anthropic, or any OpenAI-compatible server such
> as Ollama or vLLM); local development uses `codex/gpt-6-luna` through the sub2api gateway.

## Quickstart

```bash
make install    # Python and web dependencies; creates .env (pick the LLM provider there)
make up         # Postgres, Qdrant, API (:8000) and chat UI: open http://localhost:5173
make down       # stop everything (stored conversations are kept)
```

`make` lists every command, including `make restart`, `make status`, `make logs` and `make ci`
(the CI pipeline, run locally).

Behind a reverse proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy IP>` so
rate limits apply per user rather than per proxy.

## Tests

| Layer | Command | Needs |
|-------|---------|-------|
| Unit | `uv run pytest tests/unit` | nothing |
| AI (evals) | `uv run pytest tests/ai` | LLM API keys |
| End-to-end | `uv run pytest tests/e2e` | `docker compose up -d`, LLM API keys |
| Web | `cd web && npm run lint && npm test -- --run && npm run build` | nothing |

See [AGENTS.md](AGENTS.md) for contributor and coding-agent guidelines.
