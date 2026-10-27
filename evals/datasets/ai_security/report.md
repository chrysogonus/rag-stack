# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `claude-code/claude-haiku-5-5` (openai-compatible) with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. 193 RAG and 193 baseline answers of 193 were asked anew; the others, and every verdict whose inputs are unchanged, are reused from earlier runs (`make eval FULL=1` asks everything again, `FRESH=1` the baseline). Scores are means in [0, 1] with 95% bootstrap intervals for RAG; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions. Settings are tuned on `dev`; `test` is the holdout.

Thresholds (`thresholds.yaml`, on the `test` row): all thresholds met.

Regressions since the run of 2026-10-26T21:38:05+00:00 (4797e1c): 

- join-contact-point: correctness 0.50 → 0.00
- join-contact-point: abstention correct → wrong

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 41 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.56 → 0.88 [0.83, 0.93] | 0.49 → 0.90 [0.83, 0.96] | 0.73 → 1.00 [1.00, 1.00] | 0.98 [0.95, 0.99] |
| freshness | 44 | 0.95 [0.89, 1.00] | 0.82 [0.73, 0.91] | 0.61 → 0.81 [0.74, 0.87] | 0.31 → 0.70 [0.60, 0.80] | 0.86 → 1.00 [1.00, 1.00] | 0.98 [0.95, 0.99] |
| cross-source | 39 | 0.95 [0.89, 0.99] | 0.97 [0.92, 1.00] | 0.65 → 0.71 [0.60, 0.81] | 0.73 → 0.83 [0.72, 0.93] | 0.90 → 0.92 [0.82, 1.00] | 0.92 [0.86, 0.97] |
| german-legal | 25 | 1.00 [1.00, 1.00] | 0.90 [0.80, 0.98] | 0.85 → 0.98 [0.94, 1.00] | 0.59 → 0.90 [0.81, 0.98] | 0.92 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| cve | 24 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.71 → 0.76 [0.70, 0.82] | 0.10 → 1.00 [1.00, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] |
| list | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.40 → 0.95 [0.85, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 0.85 [0.75, 0.95] |
| abstention | 10 | n/a | n/a | 0.30 → 1.00 [1.00, 1.00] | n/a → n/a | 0.30 → 1.00 [1.00, 1.00] | 0.93 [0.82, 1.00] |
| follow-up | 5 | 1.00 [1.00, 1.00] | 0.70 [0.50, 0.90] | 0.70 → 0.95 [0.85, 1.00] | 0.56 → 0.96 [0.88, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| dev | 59 | 0.96 [0.91, 1.00] | 0.92 [0.85, 0.98] | 0.60 → 0.84 [0.77, 0.90] | 0.43 → 0.88 [0.79, 0.95] | 0.76 → 0.97 [0.92, 1.00] | 0.94 [0.89, 0.97] |
| test | 134 | 0.98 [0.96, 1.00] | 0.93 [0.90, 0.96] | 0.65 → 0.83 [0.80, 0.87] | 0.45 → 0.84 [0.79, 0.89] | 0.86 → 0.99 [0.98, 1.00] | 0.96 [0.95, 0.98] |
| all | 193 | 0.98 [0.96, 0.99] | 0.93 [0.90, 0.96] | 0.63 → 0.84 [0.80, 0.87] | 0.45 → 0.85 [0.81, 0.89] | 0.83 → 0.98 [0.96, 1.00] | 0.96 [0.94, 0.97] |

Per-question results, answers and judge reasons: `results.json`. 135 of 193 questions are unreviewed drafts (`needs_review: true`) generated from the indexed corpus.
