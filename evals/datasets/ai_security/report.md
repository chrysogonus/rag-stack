# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `claude-code/claude-opus-5-5` (openai-compatible) with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. Scores are means in [0, 1] with 95% bootstrap intervals for RAG; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions. Settings are tuned on `dev`; `test` is the holdout.

Thresholds (`thresholds.yaml`, on the `test` row): all thresholds met.

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 25 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.72 → 0.90 [0.85, 0.95] | 0.66 → 0.97 [0.92, 1.00] | 0.76 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| freshness | 25 | 0.76 [0.60, 0.92] | 0.64 [0.48, 0.80] | 0.49 → 0.65 [0.53, 0.76] | 0.25 → 0.60 [0.43, 0.77] | 0.76 → 0.92 [0.80, 1.00] | 0.98 [0.95, 1.00] |
| cross-source | 20 | 0.93 [0.85, 1.00] | 0.94 [0.85, 1.00] | 0.74 → 0.85 [0.70, 0.97] | 0.68 → 0.88 [0.72, 1.00] | 0.90 → 0.90 [0.75, 1.00] | 0.96 [0.89, 1.00] |
| german-legal | 25 | 1.00 [1.00, 1.00] | 0.90 [0.80, 0.98] | 0.70 → 0.95 [0.89, 1.00] | 0.50 → 0.93 [0.84, 1.00] | 0.84 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| cve | 20 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.74 → 0.74 [0.66, 0.81] | 0.50 → 1.00 [1.00, 1.00] | 0.95 → 1.00 [1.00, 1.00] | 0.99 [0.96, 1.00] |
| list | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| abstention | 10 | n/a | n/a | 0.30 → 1.00 [1.00, 1.00] | n/a → n/a | 0.20 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| follow-up | 5 | 1.00 [1.00, 1.00] | 0.70 [0.50, 0.90] | 0.55 → 0.95 [0.85, 1.00] | 0.60 → 0.96 [0.88, 1.00] | 0.80 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| dev | 59 | 0.96 [0.92, 1.00] | 0.91 [0.84, 0.96] | 0.64 → 0.83 [0.76, 0.88] | 0.50 → 0.91 [0.83, 0.97] | 0.75 → 0.97 [0.92, 1.00] | 0.98 [0.95, 1.00] |
| test | 76 | 0.92 [0.86, 0.98] | 0.87 [0.80, 0.94] | 0.62 → 0.86 [0.81, 0.91] | 0.49 → 0.86 [0.78, 0.92] | 0.79 → 0.97 [0.93, 1.00] | 1.00 [0.99, 1.00] |
| all | 135 | 0.94 [0.90, 0.98] | 0.89 [0.84, 0.93] | 0.63 → 0.84 [0.80, 0.88] | 0.49 → 0.88 [0.83, 0.93] | 0.77 → 0.97 [0.94, 0.99] | 0.99 [0.97, 1.00] |

Per-question results, answers and judge reasons: `results.json`. 135 of 135 questions are unreviewed drafts (`needs_review: true`) generated from the indexed corpus.
