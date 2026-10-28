# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `claude-code/claude-haiku-5-5` (openai-compatible) with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. 26 RAG and 16 baseline answers of 212 were asked anew; the others, and every verdict whose inputs are unchanged, are reused from earlier runs (`make eval FULL=1` asks everything again, `FRESH=1` the baseline). Scores are means in [0, 1] with 95% bootstrap intervals for RAG; judge scores map 1-5 to 0-1. Recall@k counts the first 8 passages, the ones the model sees. Retrieval metrics and citation precision skip abstention questions. Settings are tuned on `dev`; `test` is the holdout.

Thresholds (`thresholds.yaml`, on the `test` row): all thresholds met.

Regressions since the run of 2026-10-28T10:02:16+00:00 (6b61c18-dirty): none.

| Category | n | Recall@k | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 41 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.63 → 0.91 [0.86, 0.95] | 0.57 → 0.92 [0.84, 0.98] | 0.78 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| freshness | 18 | 0.94 [0.83, 1.00] | 0.72 [0.55, 0.87] | 0.76 → 0.88 [0.82, 0.93] | 0.39 → 0.85 [0.69, 0.97] | 1.00 → 1.00 [1.00, 1.00] | 0.96 [0.92, 1.00] |
| paraphrase | 27 | 0.97 [0.92, 1.00] | 0.84 [0.74, 0.94] | 0.62 → 0.93 [0.87, 0.97] | 0.31 → 0.63 [0.52, 0.73] | 0.85 → 1.00 [1.00, 1.00] | 0.97 [0.94, 1.00] |
| cross-source | 25 | 0.94 [0.86, 1.00] | 0.93 [0.85, 1.00] | 0.64 → 0.82 [0.71, 0.91] | 0.63 → 0.88 [0.76, 0.98] | 0.96 → 0.96 [0.88, 1.00] | 0.93 [0.88, 0.97] |
| relation | 14 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.75 → 1.00 [1.00, 1.00] | 0.84 → 1.00 [1.00, 1.00] | 0.86 → 1.00 [1.00, 1.00] | 0.96 [0.91, 1.00] |
| german-legal | 25 | 0.99 [0.98, 1.00] | 0.92 [0.81, 1.00] | 0.79 → 0.94 [0.90, 0.98] | 0.58 → 0.88 [0.80, 0.96] | 0.92 → 1.00 [1.00, 1.00] | 0.97 [0.92, 1.00] |
| cve | 24 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.74 → 0.82 [0.76, 0.89] | 0.12 → 1.00 [1.00, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.92 [0.86, 0.96] |
| list | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 0.90 [0.80, 1.00] |
| abstention | 16 | n/a | n/a | 0.48 → 1.00 [1.00, 1.00] | n/a → n/a | 0.31 → 1.00 [1.00, 1.00] | 0.94 [0.88, 1.00] |
| follow-up | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.70 → 0.95 [0.85, 1.00] | 0.60 → 0.90 [0.70, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.95 [0.85, 1.00] |
| injection | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.80 → 0.85 [0.75, 0.95] | 0.20 → 1.00 [1.00, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.95 [0.85, 1.00] |
| robustness | 7 | 0.86 [0.57, 1.00] | 0.86 [0.57, 1.00] | 0.82 → 0.96 [0.89, 1.00] | 0.50 → 0.79 [0.50, 1.00] | 0.86 → 1.00 [1.00, 1.00] | 0.93 [0.86, 1.00] |
| dev | 60 | 0.98 [0.94, 1.00] | 0.92 [0.85, 0.98] | 0.62 → 0.96 [0.93, 0.98] | 0.43 → 0.93 [0.88, 0.98] | 0.80 → 1.00 [1.00, 1.00] | 0.96 [0.93, 0.98] |
| test | 152 | 0.98 [0.96, 0.99] | 0.93 [0.90, 0.96] | 0.70 → 0.89 [0.86, 0.91] | 0.48 → 0.86 [0.81, 0.90] | 0.86 → 0.99 [0.98, 1.00] | 0.96 [0.94, 0.97] |
| all | 212 | 0.98 [0.96, 0.99] | 0.93 [0.90, 0.95] | 0.68 → 0.91 [0.89, 0.93] | 0.46 → 0.88 [0.84, 0.91] | 0.84 → 1.00 [0.99, 1.00] | 0.96 [0.94, 0.97] |

Per-question results, answers and judge reasons: `results.json`. 0 of 212 questions are unreviewed drafts (`needs_review: true`) generated from the indexed corpus.
