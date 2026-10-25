# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `codex/gpt-6-luna` (openai-compatible) with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. Scores are means in [0, 1]; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions.

Thresholds (`thresholds.yaml`, on the `all` row): all thresholds met.

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 10 | 1.00 | 1.00 | 0.62 → 1.00 | 0.50 → 0.93 | 0.70 → 1.00 | 1.00 |
| freshness | 10 | 0.90 | 0.75 | 0.28 → 0.90 | 0.20 → 0.85 | 0.40 → 1.00 | 0.97 |
| cross-source | 10 | 0.90 | 0.93 | 0.53 → 0.75 | 0.47 → 0.80 | 0.70 → 0.80 | 0.90 |
| german-legal | 10 | 1.00 | 0.87 | 0.65 → 1.00 | 0.60 → 0.87 | 0.80 → 1.00 | 1.00 |
| cve | 5 | 1.00 | 1.00 | 0.60 → 0.80 | 0.20 → 1.00 | 1.00 → 1.00 | 0.90 |
| list | 5 | 1.00 | 1.00 | 0.45 → 1.00 | 0.00 → 0.81 | 0.60 → 1.00 | 1.00 |
| abstention | 6 | n/a | n/a | 0.33 → 1.00 | n/a → n/a | 0.33 → 1.00 | 0.88 |
| follow-up | 3 | 1.00 | 0.83 | 0.17 → 0.92 | 0.33 → 1.00 | 1.00 → 1.00 | 0.92 |
| all | 59 | 0.96 | 0.91 | 0.48 → 0.92 | 0.37 → 0.88 | 0.66 → 0.97 | 0.96 |

Per-question results, answers and judge reasons: `results.json`. The questions are drafts (`needs_review: true`) generated from the indexed corpus.
