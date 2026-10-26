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
| `llm/embeddings.py`, `llm/fastembed_local.py`, `llm/vllm_models.py` | Embedding, sparse and reranker interfaces; local fastembed adapters (CPU) and vLLM adapters (GPU) |
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
  **Superseded on this machine (2026-10-26) by Qwen3 on the GPU:** Qwen3-Embedding-4B and
  Qwen3-Reranker-0.6B, both fp8, on vLLM v0.31.0 (`docker compose` profile `gpu`). A 4B reranker
  doesn't fit beside the 4B embedding and the Windows desktop's ~7 GB of the 16 GB RTX 5070 Ti.
  Golden-set retrieval, all 135 questions (recall@10 / MRR):

  | | e5 + bge (CPU) | e5 + Qwen3 reranker | Qwen3 embedding + reranker |
  |---|---|---|---|
  | all | 0.940 / 0.885 | 0.964 / 0.896 | 0.968 / 0.908-0.917 |
  | freshness | 0.760 / 0.630 | 0.880 / 0.709 | 0.880 / 0.790 |
  | cross-source | 0.925 / 0.942 | 0.925 / 0.967 | 0.950 / 0.950 |
  | german-legal | 1.000 / 0.901 | 1.000 / 0.879 | 1.000 / 0.879 |
  | cve | 1.000 / 1.000 | 1.000 / 0.975 | 1.000 / 1.000 |
  | retrieval p50 / p95 | 2.0 / 3.3 s | 0.51 / 0.76 s | 0.63 / 0.98 s |

  id-exact, list and follow-up are unchanged. German-legal MRR drops 0.022 (one question ranked
  lower; the reranker's doing, recall unchanged); accepted. fp8 makes MRR vary by about 0.005
  between runs, and latency rose to 2.2-2.4 s p50 while other software loaded the GPU.
  Embedding runs at 43 chunks/s (CPU: 1.9). Qwen3-Reranker returns probabilities, so
  `RERANK_MIN_SCORE` is 0.005: off-topic questions top out at 0.0-0.01, but near-domain
  abstention questions reach 0.8-0.99 and are left to the model's refusal, and several
  answerable CVE questions score 0.005-0.12 (they name their IDs, which bypass the cut-off).
  Queries are embedded without an instruction. The first eval run used a cybersecurity
  instruction, and KI-MIG § 17 Abs. 1 fell to dense rank 70, out of the 20 candidates: a German
  legal question was refused (the run history's one regression). Recall@10 / MRR on all
  questions: cybersecurity instruction 0.968 / 0.914, Qwen's default web-search instruction
  0.976 / 0.909, none 0.988 / 0.916 (freshness recall 0.88 → 0.96; cross-source MRR 0.975 →
  0.938, its recall 0.95 → 0.97). BM25 can't catch such cases: without stemming, "Behörden"
  doesn't match "Verwaltungsbehörden".
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

## Regular ingestion and incremental evals (built)

The knowledge base is to grow and refresh on a schedule. Before step 3 any change made the whole
eval stale: one fingerprint hashed every `.py` under `src/rag_stack`, the processed corpus, the
rubric, the golden set and the model settings, so a weekly CVE ingest or an API-only change
failed `make evals` until a full paid run (about 550 calls, 26-40 min). Of those
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
   **Built:** each result keeps `answer_key` (model settings, `SYSTEM_PROMPT`, the source names a
   refusal lists, and each turn's input as `model_input` in `agent/graph.py` builds it, with a
   placeholder for an earlier answer) and `judge_key`. `make eval` always retrieves and recomputes
   every score, and asks and judges only where a key changed. `make evals` runs the same eval with
   models that may not be called (`stale_questions`): a question is stale if a model would be
   called or a recomputed result differs (a changed gold ID, scoring code, a ranking change below
   the top 8, a footer rebuilt for a new source version) or a gold ID is missing from the index,
   so it needs the index and takes about 5 minutes of retrieval, no calls. The
   catalog of source names is hashed whole: adding a source makes every answer stale. Not
   hashed: request parameters set inside the provider adapters (`src/rag_stack/llm/`); after
   changing those, run `make eval FULL=1`.
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
   **Built:** `make eval` searches the generation the alias names at its start (a promotion
   mid-run doesn't switch it), records it and the source versions read from it, appends one line
   per run and lists the regressions since the previous
   line in `report.md` (an abstention turning wrong either way counts). They are reported, not
   failed on: thresholds decide pass or fail.
4. **Key-fact review flag:** when a question's gold chunk text changes (a CVE gets a fix, ATLAS
   revises a technique), the question is flagged for key-fact review, so an outdated key fact
   doesn't show up as a regression.

No random subsets: each run would score different questions, so runs aren't comparable and a
category can be missed. Item 4, the key-fact review flag, is not built.

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
checks. A refresh runs no LLM eval: after a promotion `make evals` lists the questions whose
retrieved passages changed, and `make eval` asks only those. Snapshot retention is
deferred: `data/raw` and `data/processed` grow about 0.5 GB a year with weekly CVE snapshots.
After a blocked run `LATEST` names the blocked snapshot, so a manual `make index` would index it.

A new source needs a parser, an allowlist entry and dev and test questions (`make eval-draft`);
its questions then fall under the per-question fingerprints like the rest.

### Order

1. Scheduled ingestion with the diff gates and the free retrieval eval: regression tracking for
   ingestion at no LLM cost. Built.
2. Baseline caching: halves a full run. Built.
3. Per-question fingerprints and the run history. Built.

## Next: general cybersecurity research (not built)

The chatbot is to cover cybersecurity research in general, with AI security as a specialty:
about 10x the corpus (35-40k chunks), only citable sources whose licenses allow storing and
quoting them. The new sources were chosen for the joins they add between each other and with
today's: ATT&CK ↔ ATLAS ↔ CAPEC ↔ CWE ↔ CVE/KEV, ATT&CK ↔ D3FEND, Sigma and Atomic tests,
SP 800-53 ↔ CSF 2.0, NIS2 → BSIG and CRA. The ATLAS → ATT&CK and OWASP → CWE edges stored today
then lead somewhere (OPEN_QUESTIONS).

### Sources, in four waves

| Wave | id | Source and fetch | Native IDs | License |
|---|---|---|---|---|
| 1 | `attack` | MITRE ATT&CK Enterprise, Mobile, ICS: STIX 2.1 from `mitre-attack/attack-stix-data`, pinned release | `TA0002`, `T1059.001`, `M1038`, `G0016`, `S0154`, `C0024`, detection strategies | ATT&CK terms of use (keep the notice) |
| 1 | `capec` | CAPEC XML | `CAPEC-66` | CAPEC terms of use |
| 1 | `cwe` | CWE XML | `CWE-79` | CWE terms of use |
| 1 | `d3fend` | D3FEND ontology and ATT&CK mappings | `D3-MFA` | D3FEND terms of use |
| 1 | `vulns` (replaces `ai-vulns`) | One chunk per CVE: AI packages (OSV, as now), the whole CISA KEV catalog, GitHub-reviewed critical and high advisories of the last 24 months; NVD 2.0 details, FIRST EPSS scores | `CVE-…`, GHSA aliases | as now; EPSS terms to verify |
| 2 | `nist-csf` | CSF 2.0, CPRT JSON | `PR.AA-01` | US government work |
| 2 | `nist-800-53` | SP 800-53 Rev. 5, OSCAL JSON | `AC-2(1)` | US government work |
| 2 | `nist-pubs` | SP 800-218 SSDF, SP 800-61r3, AI RMF 1.0, AI 600-1, AI 100-2 E2025 (PDF) | `SSDF PO.1.1`, `AI RMF GOVERN 1.1` | US government work |
| 2 | `owasp-top10-2025`, `owasp-asvs-5`, `owasp-cheatsheets` | GitHub Markdown, pinned commits | `A01:2025`, ASVS 5.0 IDs, sheet and section | CC BY-SA 4.0 |
| 2 | `owasp-ai-exchange` | GitHub Markdown | section | to verify: the site says CC0, the project page Apache-2.0 |
| 3 | `nis2`, `cra`, `csa`, `dora` | Directive (EU) 2022/2555, Regulations (EU) 2024/2847, 2019/881, 2022/2554, EN and DE via CELLAR | `NIS2 Art. 21(2)`, `CRA Annex I` | Decision 2011/833/EU |
| 3 | `bsig` | BSIG as amended by the NIS2UmsuCG (in force 6 Dec 2025), gesetze-im-internet.de XML | `BSIG § 30 Abs. 1` | § 5 UrhG |
| 4 | `sigma` | SigmaHQ rules (core, threat hunting, emerging threats), pinned release | rule title, UUID as alias | DRL 1.1: show each rule's author |
| 4 | `atomic-red-team` | Atomic tests per ATT&CK technique | `T1059.001 atomic 3`, GUID as alias | MIT |
| 4 | `arxiv-cscr` | arXiv cs.CR, last 24 months, only papers whose comments or journal reference name an accepted top venue (list in `config/sources.yaml`): abstract and link | `arXiv:2601.01234` | metadata CC0 (arXiv API terms); 1 request per 3 s |

Left out: BSI IT-Grundschutz (licensed commercially, no free reuse terms found) and the GDPR
(the golden set's Art. 17 question is an abstention). Atomic Red Team holds executable attack
commands: they are source data for testing detections, quoted under the "sources are data" rule.

### Groundwork, before the first new source

1. **Reuse vectors per chunk.** `build_candidate` copies a served point with its vector while
   its text is unchanged and embeds only new or changed chunks; today a change re-embeds the whole
   source, which at thousands of CVEs, ATT&CK objects or papers would take hours a week.
   **Built:** `index_source(..., reuse_from=served)` compares each chunk's embedded text with its
   served point's and keeps the vectors when they match; a new source version only rewrites the
   payload.
2. **Measure** embedding throughput and retrieval latency on this machine; tighten the arXiv
   filter or the advisory window if the numbers demand it. **Measured** (16 cores, 2026-10-26):
   e5-large embeds 1.9 chunks/s (real chunks, 1,030 characters on average), BM25 6,200/s; so
   about 5 h of one-time embedding for 35k chunks. Since the switch to Qwen3-Embedding-4B on the
   GPU (see "Deviations"): 43 chunks/s, about 15 min for 35k chunks. Retrieval: p50 0.63 s,
   p95 0.98 s (135 questions), to compare after each wave.
3. **One parser per legal system:** the AI Act parser becomes an EU-law parser configured by
   CELEX and short name (AI Act IDs unchanged), the KI-MIG parser a gesetze-im-internet parser.
4. **Act-aware ID detection** (`retrieval/ids.py`): today every `Art. N` is the AI Act's and
   every `§ N` the KI-MIG's. Act names and aliases pick the act; a bare article expands to every
   indexed act and the reranker decides. New ID families for ATT&CK, CWE, CAPEC, D3FEND, NIST,
   OWASP and arXiv.
5. **Scope:** the system and baseline prompts, README and this plan's intro name general
   cybersecurity. Every eval question goes stale once; one incremental run.

Per source: a parser with a fixture test, a registry entry, an allowlist entry, its license in
`NOTICE.md`, about 5 dev and 5 test questions (`make eval-draft`, reviewed), ingest through
`make refresh`. Abstention questions that become answerable are replaced (the AI RMF one with
`nist-pubs`). Each wave ends with `make eval` and `make evals`, retrieval on the old questions
within 0.02 of before, and spot checks of the joins with `make ask`. Refresh cadence: weekly
for KEV, EPSS, advisories, arXiv and Sigma; monthly for CWE, CAPEC, D3FEND and law; pinned
releases for ATT&CK, OWASP and NIST.

Risks: retrieval quality at 10x (ATT&CK, CAPEC and Sigma near-duplicates for one technique),
the one-time embedding of about 35k chunks on CPU, and a golden set of about 300 questions
(`FULL=1` about 1,200 calls).

## Not built (out of scope)

UI changes, auth, multi-tenancy, deployment, and any source not on the allowlist. Outbound links
in ATLAS and OWASP (news, papers) are stored as metadata and never fetched.
