# rag-stack

A custom retrieval-augmented generation (RAG) application that powers a chatbot. At its core is
a knowledge base agent that answers user questions from your documents.

**How it works:** documents are ingested, chunked, and embedded into Qdrant. For each question,
the agent retrieves the most relevant chunks and writes an answer grounded in them. The LLM and
embedding providers are pluggable.

> Status: early setup. The code and the commands below are planned.

## Quickstart

```bash
uv sync
cp .env.example .env                              # add provider API keys
docker run -p 127.0.0.1:6333:6333 qdrant/qdrant   # start Qdrant (localhost only)
```

## Tests

| Layer | Command | Needs |
|-------|---------|-------|
| Unit | `uv run pytest tests/unit` | nothing |
| AI (evals) | `uv run pytest tests/ai` | LLM API keys |
| End-to-end | `uv run pytest tests/e2e` | running Qdrant |

See [AGENTS.md](AGENTS.md) for contributor and coding-agent guidelines.
