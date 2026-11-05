# Eval report: Starter handbook golden set

Chat model `gpt-6-luna` (openai); judge `claude-code/claude-haiku-5-5` (openai-compatible) with rubric `packs/starter/evals/judge.md`. Baseline: `codex/gpt-6-luna` (openai-compatible) as a general chatbot, same questions. 12 RAG and 12 baseline answers of 12 were asked anew; the others, and every verdict whose inputs are unchanged, are reused from earlier runs (`make eval FULL=1` asks everything again, `FRESH=1` the baseline). Scores are means in [0, 1] with 95% bootstrap intervals for RAG; judge scores map 1-5 to 0-1. Recall@k counts the first 8 passages, the ones the model sees. Retrieval metrics and citation precision skip abstention questions. Settings are tuned on `dev`; `test` is the holdout.

Thresholds (`thresholds.yaml`, on the `test` row): all thresholds met.

No earlier run in `history.jsonl` to compare with.

| Category | n | Recall@k | MRR | Correctness (base → RAG) | Citation precision (base → RAG) | Abstention acc. (base → RAG) | Faithfulness (RAG) |
|---|---|---|---|---|---|---|---|
| id-exact | 1 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.00 → 0.00 [0.00, 0.00] | 0.00 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| paraphrase | 6 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.00 → 0.92 [0.75, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.17 → 1.00 [1.00, 1.00] | 0.96 [0.88, 1.00] |
| cross-source | 1 | 1.00 [1.00, 1.00] | 0.50 [0.50, 0.50] | 0.00 → 1.00 [1.00, 1.00] | 0.00 → 0.50 [0.50, 0.50] | 0.00 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| relation | 1 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.75 [0.75, 0.75] |
| abstention | 2 | n/a | n/a | 1.00 → 1.00 [1.00, 1.00] | n/a → n/a | 1.00 → 1.00 [1.00, 1.00] | 0.75 [0.75, 0.75] |
| follow-up | 1 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 0.00 → 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] |
| dev | 7 | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.14 → 1.00 [1.00, 1.00] | 0.00 → 0.83 [0.50, 1.00] | 0.14 → 1.00 [1.00, 1.00] | 0.96 [0.88, 1.00] |
| test | 5 | 1.00 [1.00, 1.00] | 0.88 [0.62, 1.00] | 0.20 → 0.90 [0.70, 1.00] | 0.00 → 0.88 [0.62, 1.00] | 0.40 → 1.00 [1.00, 1.00] | 0.90 [0.80, 1.00] |
| all | 12 | 1.00 [1.00, 1.00] | 0.95 [0.85, 1.00] | 0.17 → 0.96 [0.88, 1.00] | 0.00 → 0.85 [0.60, 1.00] | 0.25 → 1.00 [1.00, 1.00] | 0.93 [0.86, 1.00] |

Per-question results, answers and judge reasons: `results.json`. 0 of 12 questions are unreviewed drafts (`needs_review: true`) generated from the indexed corpus.
