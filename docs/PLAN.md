# Plan: AI-security knowledge base

A self-hosted RAG chatbot on attacks against AI systems and EU AI regulation. It should beat a
general chatbot on three things: freshness (content newer than model training data), exact
citable IDs with verbatim legal text, and joins across sources (technique → mitigation → OWASP
risk → AI Act article → CVE).

## Sources (allowlist: `config/sources.yaml`)

| id | Source | Fetched from | Units (native IDs) |
|---|---|---|---|
| `atlas` | MITRE ATLAS | `atlas-data` `dist/v6/ATLAS-latest.yaml` (a symlink to the dated release) | tactics `AML.TA####`, techniques `AML.T####[.###]`, mitigations `AML.M####`, case studies `AML.CS####` |
| `owasp-llm-2026` | OWASP Top 10 for LLM Applications 2026 | `GenAI-LLM-Top10` `2026/final/*.md`, pinned commit | `LLM01:2026` … one chunk per `###` section |
| `owasp-agentic-2026` | OWASP Top 10 for Agentic Applications 2026 | PDF from genai.owasp.org | `ASI01` … one chunk per section |
| `eu-ai-act` | Regulation (EU) 2024/1689, EN + DE | CELLAR REST API (EUR-Lex HTML is behind a bot challenge) | `AI Act Art. 50(1)`, `Recital 133`, `Annex III 1(a)` |
| `ki-mig` | KI-Marktüberwachungs- und Innovationsförderungsgesetz | gesetze-im-internet.de XML | `KI-MIG § 2 Abs. 1` |
| `ai-vulns` | CVEs in AI packages, last 24 months | OSV (GitHub advisories), NVD API 2.0, CISA KEV | `CVE-…` (GHSA/PYSEC ids as aliases) |

## Modules

| Path | What it does |
|---|---|
| `ingestion/fetch.py` | Polite HTTP client: User-Agent, robots.txt incl. crawl-delay, per-host rate limit, retries, on-disk cache, NVD key from env |
| `ingestion/pipeline.py` | `ingest(source)`: raw snapshot + `SHA256SUMS` + `manifest.json` under `data/raw/<source>/<version>/`, chunks and edges under `data/processed/`. Unchanged input and parser code means skip |
| `ingestion/sources/*.py` | One module per source: `fetch()` and `parse()` |
| `ingestion/models.py` | `Chunk` (all citation and license metadata), `Edge`, splitting of oversized units (parts keep the native ID) |
| `db/migrations`, `db/edges.py` | Alembic migration for `kb_edges`; edge writes and the in-memory 1-hop graph |
| `llm/embeddings.py`, `llm/fastembed_local.py` | Embedding, sparse and reranker interfaces and their local fastembed adapters |
| `retrieval/index.py` | Qdrant collection (named `dense` vector + `bm25` sparse vector with IDF), per-source replace |
| `retrieval/ids.py` | Regex detection of IDs and EN/DE legal references in questions |
| `retrieval/retriever.py` | Exact IDs → dense + BM25 → RRF (k=60) → cross-encoder rerank of the top 50 → 1-hop graph expansion → same-language legal text; keeps the top 8 for the answer |
| `agent/graph.py`, `agent/prompts.py`, `agent/answer.py` | LangGraph `retrieve → generate`; delimited sources and injection rules; deterministic footer with attribution, versions and the Art. 50 AI label; abstention |
| `evals/` (`src/rag_stack/evals/`) | Metrics, LLM judge with a versioned rubric, RAG vs. no-retrieval baseline, report |
| `cli.py` | `ingest`, `index`, `ask`, `eval`, `eval-draft` (wrapped by `make`) |
| `observability.py` | Langfuse tracing (`make tracing`, self-hosted): one trace per chat turn with `retrieve` (and its id lookup, hybrid search, graph expansion, rerank and language stages) and `generate` (model, tokens); a reader's rating (`POST /api/threads/{id}/feedback`) is a `helpful` score on it. Does nothing without `LANGFUSE_*` |

## Deviations from the brief's defaults

- **Vector store: Qdrant, not pgvector.** The skeleton already chose Qdrant hybrid search.
- **BM25 in Qdrant (sparse vectors with the IDF modifier), not Postgres FTS.** Dense and BM25 run
  as one batched Qdrant request; the RRF fusion (k=60) is ours, so it is exact and unit-tested.
- **Edge table in Postgres via Alembic.** AGENTS.md plans `db/` with Alembic; the API holds the
  table in memory for 1-hop lookups.
- **Dense model: `intfloat/multilingual-e5-large`, not `BAAI/bge-m3`.** fastembed (ONNX, no
  torch) has no bge-m3; e5-large is its strongest multilingual model. Both are settings.
- **Reranker: the int8 build of `BAAI/bge-reranker-v2-m3`, reading the first 1000 characters of
  each candidate.** On this machine's CPU the full-precision model took 35-50 s to rerank 50
  candidates; int8 with the cut takes 6-8 s with near-identical top 5s (measured on three
  questions). `RERANKER_MODEL` and `RERANK_MAX_CHARS` switch back. Later cut to 20 candidates
  of 800 characters: retrieval p50 2.6 s, p95 4.1 s (was 7.9 / 11.2 s) with unchanged golden
  recall@10 and MRR; `jina-reranker-v2-base-multilingual` was no faster at equal quality.
- **BM25 without stemming.** The corpus mixes English and German; an English stemmer would
  mangle German terms.
- **Eval paths follow AGENTS.md, not `eval/`.** `evals/datasets/ai_security/golden.jsonl` (JSONL,
  like the earlier dataset), `thresholds.yaml`, `report.md`, `results.json`; the rubric is
  `evals/rubrics/judge_v1.md`. `make eval` writes the report; `make evals` runs `tests/ai`, which
  asserts the thresholds with the same harness.
- **Eval baseline: a live general chatbot, not the same model without retrieval.** RAG runs on
  the OpenAI API (`gpt-6-luna`); the baseline is the sub2api gateway (`codex/gpt-6-luna`), which
  can search the web, as the reference a user would otherwise ask. `EVAL_BASELINE_*` configures
  it; unset, the baseline is the RAG model without retrieval as the brief describes.
- **Answer UI.** The existing web UI renders Markdown, so citation links work there unchanged;
  `make ask` is the CLI.
- **Abstention wording.** Always exactly "I can't answer that from the indexed sources." (machine
  checkable); the list of indexed sources after it is in the user's language.
- **Articles and annexes from the consolidated text, recitals from the Official Journal.**
  Consolidated versions omit recitals. The consolidated version used is `02024R1689-20260727`.
- **Article 3 definitions and unnumbered lists** are cited as `AI Act Art. 3(1)` etc., the way
  people quote them; numbered paragraphs keep their own chunk with their points inside.
- **ATLAS case-study procedures stay in the case-study text.** They are the case study's own
  narrative; the `employs` relationships are also in the edge table.
- **Package list.** `llama-index-core` is added next to `llama-index`: most llama-index
  advisories are filed against the core package.
- **Prompt-injection defense.** Sources are wrapped in `<source>` blocks, any `<source`/`</source`
  inside chunk text is defused, and the system prompt says sources are data. A unit test checks
  the block structure with an injected chunk; an AI test checks the real LLM doesn't obey it.
- **Follow-up questions** reuse the IDs of the previous question when they name none (no LLM
  query rewrite yet).

## Not built (out of scope)

UI changes, auth, multi-tenancy, deployment, and any source not on the allowlist. Outbound links
in ATLAS and OWASP (news, papers) are stored as metadata and never fetched.
