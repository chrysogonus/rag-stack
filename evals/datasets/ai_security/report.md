# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `gpt-6-luna` with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. Scores are means in [0, 1]; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions.

Thresholds (`thresholds.yaml`, on the `all` row): all thresholds met.

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 10 | 1.00 | 1.00 | 0.78 → 0.95 | 0.70 → 0.93 | 1.00 → 1.00 | 1.00 |
| freshness | 10 | 0.90 | 0.75 | 0.38 → 0.85 | 0.30 → 0.85 | 0.60 → 1.00 | 1.00 |
| cross-source | 10 | 0.90 | 0.93 | 0.45 → 0.78 | 0.47 → 0.80 | 0.60 → 0.80 | 0.90 |
| german-legal | 10 | 1.00 | 0.87 | 0.65 → 0.85 | 0.55 → 0.87 | 0.90 → 1.00 | 1.00 |
| cve | 5 | 1.00 | 1.00 | 0.60 → 0.65 | 0.20 → 1.00 | 1.00 → 1.00 | 1.00 |
| list | 5 | 1.00 | 1.00 | 0.70 → 1.00 | 0.00 → 1.00 | 0.80 → 1.00 | 1.00 |
| abstention | 6 | n/a | n/a | 0.33 → 1.00 | n/a → n/a | 0.33 → 1.00 | 1.00 |
| follow-up | 3 | 1.00 | 0.83 | 0.50 → 0.92 | 0.33 → 1.00 | 0.67 → 1.00 | 1.00 |
| all | 59 | 0.96 | 0.91 | 0.55 → 0.87 | 0.42 → 0.90 | 0.75 → 0.97 | 0.98 |

Per-question results, answers and judge reasons: `results.json`. The questions are drafts (`needs_review: true`) generated from the indexed corpus.
