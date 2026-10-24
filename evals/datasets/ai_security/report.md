# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `gpt-6-luna` with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. Scores are means in [0, 1]; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions.

Thresholds (`thresholds.yaml`, on the `all` row): all thresholds met.

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 10 | 1.00 | 1.00 | 0.45 → 0.95 | 0.23 → 1.00 | 0.70 → 1.00 | 1.00 |
| freshness | 10 | 0.90 | 0.85 | 0.28 → 0.72 | 0.15 → 0.78 | 0.40 → 0.90 | 1.00 |
| cross-source | 10 | 0.90 | 1.00 | 0.40 → 0.78 | 0.45 → 0.80 | 0.50 → 0.80 | 0.90 |
| german-legal | 10 | 1.00 | 0.85 | 0.75 → 0.95 | 0.65 → 0.80 | 0.90 → 1.00 | 0.95 |
| cve | 5 | 1.00 | 1.00 | 0.75 → 0.75 | 0.20 → 1.00 | 1.00 → 1.00 | 1.00 |
| abstention | 5 | n/a | n/a | 0.20 → 1.00 | n/a → n/a | 0.20 → 1.00 | 1.00 |
| all | 50 | 0.96 | 0.93 | 0.47 → 0.85 | 0.35 → 0.86 | 0.62 → 0.94 | 0.97 |

Per-question results, answers and judge reasons: `results.json`. The questions are drafts (`needs_review: true`) generated from the indexed corpus.
