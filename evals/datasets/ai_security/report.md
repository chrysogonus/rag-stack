# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `claude-code/claude-haiku-5-5` (openai-compatible) with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. 131 RAG and 0 baseline answers of 135 were asked anew; the others, and every verdict whose inputs are unchanged, are reused from earlier runs (`make eval FULL=1` asks everything again, `FRESH=1` the baseline). Scores are means in [0, 1] with 95% bootstrap intervals for RAG; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions. Settings are tuned on `dev`; `test` is the holdout.

Thresholds (`thresholds.yaml`, on the `test` row): all thresholds met.

Regressions since the run of 2026-10-26T16:47:13+00:00 (f5721fc): 

- freshness-ki-mig-17-abs-1: correctness 0.75 → 0.00
- freshness-ki-mig-17-abs-1: abstention correct → wrong

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 25 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.51 → 0.92 [0.87, 0.96] | 0.64 → 0.92 [0.83, 1.00] | 0.72 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| freshness | 25 | 0.88 [0.76, 1.00] | 0.77 [0.61, 0.91] | 0.50 → 0.74 [0.64, 0.83] | 0.23 → 0.58 [0.44, 0.73] | 0.80 → 0.96 [0.88, 1.00] | 0.97 [0.91, 1.00] |
| cross-source | 20 | 0.95 [0.88, 1.00] | 0.97 [0.93, 1.00] | 0.51 → 0.89 [0.76, 0.99] | 0.48 → 0.90 [0.75, 1.00] | 0.65 → 0.95 [0.85, 1.00] | 0.95 [0.86, 1.00] |
| german-legal | 25 | 1.00 [1.00, 1.00] | 0.88 [0.77, 0.97] | 0.74 → 0.97 [0.92, 1.00] | 0.60 → 0.90 [0.81, 0.98] | 0.88 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| cve | 20 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.68 → 0.72 [0.66, 0.79] | 0.47 → 1.00 [1.00, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.96 [0.93, 1.00] |
| list | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.55 → 0.95 [0.85, 1.00] | 0.00 → 0.81 [0.44, 1.00] | 0.60 → 1.00 [1.00, 1.00] | 0.95 [0.85, 1.00] |
| abstention | 10 | n/a | n/a | 0.40 → 1.00 [1.00, 1.00] | n/a → n/a | 0.40 → 1.00 [1.00, 1.00] | 0.88 [0.71, 1.00] |
| follow-up | 5 | 1.00 [1.00, 1.00] | 0.70 [0.50, 0.90] | 0.35 → 0.90 [0.80, 1.00] | 0.20 → 1.00 [1.00, 1.00] | 0.60 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| dev | 59 | 0.96 [0.92, 1.00] | 0.92 [0.85, 0.97] | 0.56 → 0.86 [0.79, 0.91] | 0.47 → 0.86 [0.77, 0.95] | 0.75 → 0.98 [0.95, 1.00] | 0.96 [0.92, 0.99] |
| test | 76 | 0.97 [0.93, 1.00] | 0.91 [0.84, 0.96] | 0.57 → 0.88 [0.84, 0.92] | 0.44 → 0.85 [0.78, 0.91] | 0.78 → 0.99 [0.96, 1.00] | 0.98 [0.95, 1.00] |
| all | 135 | 0.97 [0.94, 0.99] | 0.91 [0.87, 0.95] | 0.56 → 0.87 [0.83, 0.90] | 0.45 → 0.86 [0.80, 0.91] | 0.76 → 0.99 [0.96, 1.00] | 0.97 [0.95, 0.99] |

Per-question results, answers and judge reasons: `results.json`. 135 of 135 questions are unreviewed drafts (`needs_review: true`) generated from the indexed corpus.
