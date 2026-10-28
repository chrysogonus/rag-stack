# Open questions

Things the MVP could not settle, with what was done instead.

## Sources

- **KI-MIG text authority.** The law is official as BGBl. 2026 I Nr. 223 (in force 29 July
  2026), but the Bundesgesetzblatt (recht.bund.de) publishes it only as PDF. The ingested text is
  the official XML from gesetze-im-internet.de (Federal Ministry of Justice). Its footnote says
  "Nachgewiesener Text dokumentarisch noch nicht bearbeitet": the documentation has not been
  fully processed yet. Re-ingest when that note disappears. The short title matches the brief
  (KI-MIG); the long title is "Gesetz zur Marktüberwachung und Innovationsförderung von
  künstlicher Intelligenz" (Article 1 of the "Gesetz zur Durchführung der Verordnung (EU)
  2024/1689").
- **EUR-Lex HTML is behind a bot challenge** (HTTP 202 with an empty body for scripted clients).
  The AI Act is fetched through the CELLAR REST API from publications.europa.eu instead: same
  documents, official Publications Office endpoint.
- **AI Act consolidated vs. authentic text.** Articles and annexes come from the consolidated
  version 02024R1689-20260727 (which includes amending Regulation (EU) 2026/1744); recitals come
  from the Official Journal text, because consolidated versions drop them. Only the OJ text is
  legally authentic. Should answers say so when they quote consolidated text?
- **NVD rate limit.** Without an API key NVD allows 5 requests per 30 s and answers HTTP 429
  often even at that pace. The KEV CVEs come in pages of 2,000; the AI-package CVEs not in KEV
  are asked one by one. In the 2026-10-27 snapshot all 1,758 KEV CVEs and 380 of the 382
  AI-package CVEs have an NVD record. A CVE whose lookup fails is indexed from its GitHub
  advisory alone (no NVD CVSS). Setting `NVD_API_KEY` avoids the slowness.
- **CVE "Affected" lines come from OSV version ranges.** They name the package the advisory was
  filed under, which is not always the one to upgrade: CVE-2026-26013 is listed against
  langchain-core, but its fix ships in langchain-openai 1.1.9 (requiring langchain-core 1.2.11),
  as the advisory text says. Answers should follow the advisory text; the golden set does.
- **OWASP Agentic PDF parsing.** Sections are found by their headings in the extracted PDF text,
  and page breaks inside a paragraph leave extra blank lines. A Markdown source would be more
  robust if OWASP publishes one.

## Licensing

- **CC BY-SA 4.0 share-alike.** Answers that quote OWASP text are adaptations of CC BY-SA
  material. The footer attributes and names the license; whether answers must also be offered
  under CC BY-SA should be checked before a public deployment.

## Eval

- **The baseline is a live chatbot, by choice.** The RAG side runs on the OpenAI API
  (`gpt-6-luna`); the baseline is the subscription gateway (formerly sub2api;
  `codex/gpt-6-luna`), standing in for a general chatbot as people use it. Its Codex backend
  searches the web: in the first eval runs
  (when the gateway was also the RAG model) its session logs in `~/.codex/sessions/` showed web
  searches in 50 of 101 baseline sessions and none in RAG-answer or judge sessions. So the
  comparison is "RAG vs. a chatbot that may search the web", not the brief's "same model without
  retrieval". Unset `EVAL_BASELINE_*` to get that variant.
- **The judge is `claude-code/claude-haiku-5-5` on the subscription gateway** (`EVAL_JUDGE_*`),
  another model family than the RAG model (`gpt-6-luna`), so it has no reason to favor RAG
  answers, and fast and cheap enough to run often. A small model is likelier to miss whether an
  answer states a key fact or only touches its topic, so `make eval-agreement` should confirm it
  against `claude-code/claude-opus-5-5`, which judged the runs before it. On 2026-10-28 it
  agreed with the 40 labels in `judge_labels.jsonl` exactly on 0.88 and within one point on 0.97,
  0.10 points stricter on average; the one larger miss (`german-legal-ai-act-art-79-4:baseline`,
  3 vs. 5) is a correct verbatim quote it marked down without sources to check it against. The
  labels are not human, though: Claude (Opus 5.5) set them against the primary sources
  (`judge_labels.md`), so this measures Haiku against Opus; a person should go over them. It
  runs through Claude Code (`claude --print`, no tools), not the raw Anthropic API, and
  subscription use is personal only. Runs judged by another model are not directly comparable.
- **Recall counts what the model sees.** Since 2026-10-28 the retriever returns
  `RETRIEVAL_TOP_K` (8) passages and recall is scored on them; runs before scored the first 10,
  of which the model saw 8, so their recall in `history.jsonl` is not directly comparable.
- **Terse answers cost correctness.** Several RAG answers give only the ID and title
  ("[AML.T0131] Crafted AI Assistant Links.") while the sources hold the details the key facts
  expect. The system prompt says "be concise"; asking for the relevant details from the source is
  the likely fix, to be checked on new questions rather than tuned against this set.

## Tracing

- **Traces hold questions, answers and retrieved passages.** They stay on the machine (self-hosted
  Langfuse), and no user id is sent: a hashed IPv4 address is easy to reverse. A public
  deployment needs a retention policy before tracing is turned on.
- **No cost per turn.** The chat interface reports total tokens only, so Langfuse can't price a
  generation; reporting input and output tokens separately (all three adapters have them) would.
- **Ratings use the chat rate limit** (they're cheap, but anonymous), and are only possible while
  tracing is on: otherwise the API answers 503 rather than dropping them.

## Product

- **Golden set review.** On 2026-10-28 Claude (Opus 5.5), acting as a domain expert, reviewed all
  212 questions against the indexed text and edges: 122 stood, 90 were fixed, none dropped
  (`evals/datasets/ai_security/review_2026-10-28.md` has each verdict and the source checked).
  Most fixes split compound key facts, which the judge scores all-or-nothing, or dropped facts
  the question doesn't ask for; a few corrected legal and CVE claims. All questions now carry
  `needs_review: false`, but no person has reviewed them: spot-check the log before thresholds
  are raised. (An earlier model review on 2026-10-27 covered the 135 drafts of then.)
- **Follow-up questions** reuse the IDs of the previous question when they name none; there is no
  LLM query rewrite yet.
- **English questions about German-only text.** KI-MIG exists only in German, and the AI Act's
  English articles outrank it for English questions. A question that names an act without a
  section ("under the KI-MIG") is now also searched within that act, and its two best hits keep
  a place (on dev, the KI-MIG authority and contact-point questions now find their sections).
  An English question about KI-MIG content that doesn't name the law still depends on the
  multilingual models; a query translation step would cover it.
- **Cross-source misses left.** Where search hits of one source crowd out a linked unit without
  an ID in the question (D3-FIM, D3-APCA for ATT&CK techniques; AI Act Art. 30(2) referenced
  from KI-MIG § 3), the unit misses the eight passages the model sees. Giving graph neighbors
  fixed places among the hits was tried and left out: it showed no gain on dev and cost a
  generated title check (a title containing "Hardening" counts as a relation question).
  Answers that decline or leave out key facts although the sources hold them need prompt work,
  checked with a paid eval.
- **The reranker floor was calibrated on the golden set.** On CPU (bge-reranker-v2-m3,
  `RERANK_MIN_SCORE=0`) off-topic questions top out near -1 and answerable ones start above 1;
  on GPU (Qwen3-Reranker-0.6B, scores in [0, 1]) the floor is 0.005, set with the switch and
  checked by the eval runs since. That is the set it is evaluated on, so the abstention numbers
  are optimistic until it is checked on held-out questions.
- **Language detection** is a small EN/DE word-list heuristic; very short or mixed questions can
  be misclassified, which affects only the footer language and which legal-text language is
  preferred.
- **Local models on CPU.** The reranker dominates latency on CPU, the default. With an NVIDIA GPU
  the `gpu` profile runs embeddings and reranking on vLLM instead (README); the API, refreshes
  and evals then depend on both services being up.
