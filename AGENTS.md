# AGENTS.md

## Project

A custom RAG application that powers a chatbot. At its core is the **knowledge base
agent**: it takes a user question, retrieves relevant chunks from the knowledge base, and
writes an answer grounded in them.

## Stack

- Python, managed with `uv`; tests with `pytest`
- Qdrant as the vector store
- LLM and embedding providers sit behind interfaces in `src/rag_stack/llm/`. All
  provider-specific SDK code lives there, so the rest of the code stays provider-agnostic.

## Layout (planned)

```
src/rag_stack/
  ingestion/   # load, chunk, embed documents into Qdrant
  retrieval/   # query Qdrant, rank and filter chunks
  agent/       # knowledge base agent: orchestration, prompts, tools
  llm/         # provider interfaces and adapters
tests/
  unit/        # tight: no network, LLM/embeddings/Qdrant faked
  ai/          # evals against a real LLM, marked @pytest.mark.ai
  e2e/         # question -> chatbot answer, real Qdrant
evals/datasets/  # golden Q&A sets used by tests/ai
```

## Commands

```
uv sync
uv run pytest tests/unit
uv run pytest tests/ai     # needs provider API keys in .env
uv run pytest tests/e2e    # needs Qdrant running (docker)
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
