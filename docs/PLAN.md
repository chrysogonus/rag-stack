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
| `cli.py` | `ingest`, `index`, `refresh`, `rollback`, `ask`, `eval`, `eval-draft` (wrapped by `make`) |
| `refresh.py`, `retrieval/generations.py` | Scheduled refresh: diff against the served index, checks, a candidate generation behind the `kb_chunks` alias, retrieval scores, promote or block, rollback |
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

## Next: regular ingestion and incremental evals (step 1 built)

The knowledge base is to grow and refresh on a schedule. Today any change makes the whole eval
stale: `fingerprint()` in `evals/harness.py` hashes every `.py` under `src/rag_stack`, the
processed corpus, the rubric, the golden set and the model settings, so a weekly CVE ingest or an
API-only change fails `make evals` until a full paid run (about 550 calls, 26-40 min). Of those
calls, half are the baseline answer and its judge call, which no change to our code or corpus
affects. The goal is to track regressions on every change while paying only for what changed.

### Incremental evals

Retrieval is deterministic and free, so it always runs on all questions. A question's answer and
score stay valid while its inputs are unchanged; only questions whose inputs changed are answered
and judged again.

1. **Per-question fingerprints** instead of one for the run, as hashes of the exact model inputs
   rather than a list of things that might matter. Two per side:
   - *generation*: the serialized messages sent to the model (system prompt, the sources block as
     `build_sources_block` renders it, with URLs, titles and `relation`, in order), plus the model
     settings. For a follow-up, the previous turn's inputs too: its generated answer is in the
     history, so a follow-up is stale whenever its previous turn is.
   - *judging*: the judge's input (question, previous question, key facts, answer, sources), the
     rubric and the judge model. Corrected key facts re-judge without re-answering.

   `make eval` re-runs only stale questions (`FULL=1` re-runs all); `make evals` fails only if a
   question is stale. Parser, prompt and graph-expansion changes need no rule of their own: they
   change the hashed inputs.
2. **Cache baseline answers and their judge scores** under the same two fingerprints:
   `BASELINE_PROMPT`, the question and its follow-up history, and the baseline model for the
   answer; the judge input, rubric and judge model for the score. A full run then costs about half.
   **Built:** each result in `results.json` keeps `baseline_key` and `baseline_judge_key`; a run
   reuses the saved answer and verdict while they match, and the report says how many it reused.
   `make eval FRESH=1` asks the baseline again, e.g. to refresh a web-searching chatbot's answers.
3. **Run history** (`evals/datasets/ai_security/history.jsonl`): date, commit, source versions,
   per-question scores and the summary for every run. A regression is a paired, per-question
   change: correctness down 2 points or more, or a correct refusal that turns into an answer.
   Means alone hide it: the test split's correctness interval is 0.80-0.90 (95%, n=76).
4. **Key-fact review flag:** when a question's gold chunk text changes (a CVE gets a fix, ATLAS
   revises a technique), the question is flagged for key-fact review, so an outdated key fact
   doesn't show up as a regression.

No random subsets: each run would score different questions, so runs aren't comparable and a
category can be missed. Until (1) exists, a fixed, stratified smoke set of about 30 dev questions,
RAG side only (about 60 calls, 5 min), is the interim check; the test split stays for full runs.

| Trigger | Checks | Cost |
|---|---|---|
| Every commit | Unit tests and CI, as now | free |
| Every ingest, every retrieval change | `make eval-retrieval` on all questions, gold-ID presence (`missing_gold_ids`), ingest gates below | free, minutes |
| Prompt, agent or LLM change; an ingest that changed retrieved passages | Stale questions only, RAG side | about 2 calls per question |
| Milestone, model or rubric change, monthly | Full run of all 135 questions with the baseline (today's `make eval`) | about 270 calls with the cached baseline |

### Scheduled ingestion

| Source | Cadence | Notes |
|---|---|---|
| `ai-vulns` | daily to weekly | Set `NVD_API_KEY`: without it NVD is paced at 6.5 s per request |
| `atlas` | weekly | Follows `ATLAS-latest.yaml`; releases come monthly to quarterly |
| `eu-ai-act` | monthly | The SPARQL query finds the latest consolidated version |
| `ki-mig` | monthly | Re-ingest once the "dokumentarisch noch nicht bearbeitet" note is gone (OPEN_QUESTIONS) |
| `owasp-llm-2026`, `owasp-agentic-2026` | manual | Pinned on purpose: bump the commit or PDF deliberately; check quarterly for a new release |

**Built (step 1):** `make refresh` (`src/rag_stack/refresh.py`), run weekly by a systemd user
timer (`make schedule`; Sunday 03:00, or at the next start if the machine or WSL was off). All
sources run on that one schedule: unchanged ones are skipped at ingest.

1. `make ingest SOURCE=all`; a source whose fetch or parse fails keeps its previous snapshot.
2. Diff native IDs per source against what is served (payloads in Qdrant): added, removed, changed.
3. Checks before building, any of which blocks: a source with no snapshot, a drop of more than
   10% in chunks or IDs (`FORCE=1` allows it), a gold ID of the golden set missing.
4. Build a candidate *generation*: a Qdrant collection `kb_chunks_<generation>` and its edges in
   `kb_edges` under the same `generation` (migration 0002). Unchanged sources are copied from the
   served collection with their vectors; only changed ones are embedded. Chunks and edges move
   together because graph expansion joins them.
5. Score retrieval (recall@10, MRR, all questions, no LLM) on the candidate and the served
   generation. Blocks below `thresholds.yaml` or more than 0.02 below the served generation: the
   thresholds sit far below today's scores, so only the relative check catches a regression.
6. Promote: the alias `kb_chunks` moves to the candidate and `kb_chunks_previous` to what was
   served, in one atomic change; the alias is the only pointer (the served edge generation is
   read from its target). `make refresh` then restarts the API if it runs, since `EdgeGraph` loads
   the edges at startup. `make rollback` swaps the two (again to undo). A blocked candidate is kept
   until the next run; older generations are deleted.
7. One line per run in `data/refresh.log` (PROMOTED, BLOCKED, NO CHANGE or FAILED with the
   changes and scores); `make status` shows the last one and the next run.

The first refresh adopts the collection indexed before generations (copied, counted, then
replaced by the alias). `make index` still indexes in place into the served generation, without
checks. Not yet built: the stale-question step (step 3), so the gateway isn't needed yet, and
`make evals` reports "corpus changed" after each promotion until then. Snapshot retention is
deferred: `data/raw` and `data/processed` grow about 0.5 GB a year with weekly CVE snapshots.
After a blocked run `LATEST` names the blocked snapshot, so a manual `make index` would index it.

A new source needs a parser, an allowlist entry and dev and test questions (`make eval-draft`);
its questions then fall under the per-question fingerprints like the rest.

### Order

1. Scheduled ingestion with the diff gates and the free retrieval eval: regression tracking for
   ingestion at no LLM cost. Built.
2. Baseline caching: halves a full run. Built.
3. Per-question fingerprints and the run history.

## Not built (out of scope)

UI changes, auth, multi-tenancy, deployment, and any source not on the allowlist. Outbound links
in ATLAS and OWASP (news, papers) are stored as metadata and never fetched.
