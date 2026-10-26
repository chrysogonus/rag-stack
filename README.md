# rag-stack

A self-hosted RAG chatbot on attacks against AI systems and EU AI regulation. It answers from six
openly licensed sources and cites every claim with its exact ID (ATLAS technique, OWASP risk,
AI Act provision, KI-MIG section, CVE), quoting legal text verbatim in English or German.

**How it works:** sources are fetched politely, snapshotted with sha256 and chunked one unit per
chunk (technique, risk section, article paragraph, recital, annex point, advisory). Chunks are
embedded into Qdrant (dense `multilingual-e5-large` + BM25), and relationships between IDs go into
a Postgres edge table. For each question the agent looks up IDs named in it, runs hybrid search
fused with RRF, reranks with a cross-encoder, follows edges for questions about related items,
and answers only from the retrieved chunks. Each answer ends with its sources, their licenses and
versions, and an AI-generated label (EU AI Act Art. 50(1)).

| Source | Version indexed | License |
|---|---|---|
| MITRE ATLAS | content version from the release (2026.09 at the last ingest) | Apache-2.0 |
| OWASP Top 10 for LLM Applications 2026 | `2026/final`, pinned commit | CC BY-SA 4.0 |
| OWASP Top 10 for Agentic Applications 2026 | PDF of 2025-12-09 | CC BY-SA 4.0 |
| EU AI Act (EN, DE) | latest consolidated version (02024R1689-20260727), recitals from the OJ | © EU, Decision 2011/833/EU |
| KI-MIG | gesetze-im-internet.de XML (BGBl. 2026 I Nr. 223) | § 5 UrhG |
| AI package CVEs | last 24 months, OSV + NVD + CISA KEV | CC BY 4.0 / public domain / CC0 |

See [NOTICE.md](NOTICE.md) for attribution, [docs/PLAN.md](docs/PLAN.md) for the design and
[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) for what is unresolved.

## Quickstart

```bash
make install                 # Python and web dependencies; creates .env (pick the LLM provider there)
make services                # Postgres and Qdrant
make ingest SOURCE=all       # fetch, snapshot and chunk the sources (unchanged ones are skipped)
make index                   # create the edge table, embed chunks into Qdrant (models download once)
make refresh                 # later updates: ingest, check, build and score a new index, serve it if it passes
make schedule                # run `make refresh` weekly (systemd user timer); `make rollback` undoes a refresh
make ask Q="Which ATLAS mitigations address AML.T0051?"
make up                      # API (:8000) and chat UI: open http://localhost:5173
make tracing                 # optional: self-hosted Langfuse at http://localhost:3000 (traces, ratings)
make eval                    # golden set, RAG vs. baseline, only changed questions -> evals/datasets/ai_security/report.md
make eval-retrieval          # retrieval only, free: tune on the dev split, confirm with SPLIT=test
make eval-draft SOURCE=atlas CATEGORY=freshness N=5   # draft test questions for review -> drafts.jsonl
make eval-labels             # 40 answers to label yourself; then `make eval-agreement` scores the judge
make down                    # stop everything (stored conversations and the index are kept)
```

The CVE source queries NVD once per CVE; without `NVD_API_KEY` in `.env` NVD allows 5 requests
per 30 seconds, so the first ingest of `ai-vulns` takes about an hour (responses are cached).

**GPU models (optional).** With an NVIDIA GPU, embeddings and reranking run on two vLLM
services (`docker compose` profile `gpu`): Qwen3-Embedding-4B and Qwen3-Reranker-0.6B, both
fp8. Put this into `.env`, then run `make refresh` (a new embedding model rebuilds the whole
index, scored against the old one):

```bash
COMPOSE_PROFILES=gpu
EMBEDDING_PROVIDER=vllm
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-4B
EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1
RERANKER_PROVIDER=vllm
RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B
RERANKER_BASE_URL=http://127.0.0.1:8002/v1
RERANK_MIN_SCORE=0.005
```

Together they take about 8 GB of VRAM (`EMBEDDINGS_GPU_SHARE`, `RERANKER_GPU_SHARE` set each
one's share of the card; vLLM doesn't start unless that much is free). The API, `make refresh`
and the evals then need both services; other GPU work slows retrieval down. `make rollback`
after the switch also needs the old settings back in `.env`: queries are embedded with the
configured model.

`make` lists every command, including `make restart`, `make status`, `make logs` and `make ci`
(the CI pipeline, run locally).

Behind a reverse proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy IP>` so
rate limits apply per user rather than per proxy.

## Tests

| Layer | Command | Needs |
|-------|---------|-------|
| Unit | `make test` | nothing (fixtures in `tests/fixtures/`, in-memory Qdrant, fake models) |
| AI (evals) | `make eval` (paid: ~2 calls per question whose inputs changed, ~550 with `FULL=1`), then `make evals` | LLM access, an indexed knowledge base; `make evals` checks the saved results (~5 min of retrieval, 1 call) and fails if any question is stale |
| End-to-end | `make e2e` | `make services`, LLM access, embedding models; the rating test also `make tracing` (skipped without `LANGFUSE_*`) |
| Web | `make web-check` | nothing |

See [AGENTS.md](AGENTS.md) for contributor and coding-agent guidelines.
