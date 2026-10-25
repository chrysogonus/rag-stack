# Eval report: AI-security golden set

Chat model `gpt-6-luna` (openai); judge `codex/gpt-6-luna` (openai-compatible) with rubric `evals/rubrics/judge_v1.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. Scores are means in [0, 1] with 95% bootstrap intervals for RAG; judge scores map 1-5 to 0-1. Retrieval metrics and citation precision skip abstention questions. Settings are tuned on `dev`; `test` is the holdout.

Thresholds (`thresholds.yaml`, on the `dev` row): all thresholds met. No test questions yet: settings were tuned on these dev questions, so they overstate quality on unseen ones.

| Category | n | Recall@10 | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 10 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.60 → 1.00 [1.00, 1.00] | 0.50 → 0.93 [0.78, 1.00] | 0.70 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| freshness | 10 | 0.90 [0.70, 1.00] | 0.75 [0.50, 0.95] | 0.33 → 0.88 [0.75, 0.97] | 0.23 → 0.85 [0.60, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| cross-source | 10 | 0.90 [0.75, 1.00] | 0.93 [0.80, 1.00] | 0.40 → 0.75 [0.45, 0.95] | 0.40 → 0.80 [0.50, 1.00] | 0.50 → 0.80 [0.50, 1.00] | 0.97 [0.93, 1.00] |
| german-legal | 10 | 1.00 [1.00, 1.00] | 0.87 [0.69, 1.00] | 0.55 → 0.95 [0.88, 1.00] | 0.45 → 0.87 [0.69, 1.00] | 0.80 → 1.00 [1.00, 1.00] | 0.97 [0.93, 1.00] |
| cve | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.65 → 0.95 [0.85, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.95 [0.85, 1.00] |
| list | 5 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 0.00 → 0.81 [0.44, 1.00] | 0.60 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| abstention | 6 | n/a | n/a | 0.33 → 1.00 [1.00, 1.00] | n/a → n/a | 0.33 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| follow-up | 3 | 1.00 [1.00, 1.00] | 0.83 [0.50, 1.00] | 0.17 → 0.92 [0.75, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 1.00 → 1.00 [1.00, 1.00] | 0.92 [0.75, 1.00] |
| dev | 59 | 0.96 [0.92, 1.00] | 0.91 [0.84, 0.96] | 0.45 → 0.92 [0.86, 0.97] | 0.30 → 0.88 [0.78, 0.95] | 0.63 → 0.97 [0.92, 1.00] | 0.98 [0.96, 1.00] |
| all | 59 | 0.96 [0.92, 1.00] | 0.91 [0.84, 0.96] | 0.45 → 0.92 [0.86, 0.97] | 0.30 → 0.88 [0.78, 0.95] | 0.63 → 0.97 [0.92, 1.00] | 0.98 [0.96, 1.00] |

Per-question results, answers and judge reasons: `results.json`. 59 of 59 questions are unreviewed drafts (`needs_review: true`) generated from the indexed corpus.
