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
  often even at that pace. Retries got through on the 2026-10-24 ingest: 381 of 383 CVEs have an
  NVD record (NVD returned none for the other two). A CVE whose lookup fails is indexed from its
  GitHub advisory alone (no NVD CVSS). Setting `NVD_API_KEY` avoids the slowness.
- **CVE "Affected" lines come from OSV version ranges.** They name the package the advisory was
  filed under, which is not always the one to upgrade: CVE-2026-26013 is listed against
  langchain-core, but its fix ships in langchain-openai 1.1.9 (requiring langchain-core 1.2.11),
  as the advisory text says. Answers should follow the advisory text; the golden set does.
- **OWASP Agentic PDF parsing.** Sections are found by their headings in the extracted PDF text,
  and page breaks inside a paragraph leave extra blank lines. A Markdown source would be more
  robust if OWASP publishes one.
- **Edges to frameworks outside the allowlist.** OWASP's appendix maps risks to MITRE ATT&CK and
  CWE; those edges are stored, but ATT&CK and CWE have no chunks (not on the allowlist), so graph
  expansion skips them.

## Licensing

- **CC BY-SA 4.0 share-alike.** Answers that quote OWASP text are adaptations of CC BY-SA
  material. The footer attributes and names the license; whether answers must also be offered
  under CC BY-SA should be checked before a public deployment.

## Eval

- **The baseline is a live chatbot, by choice.** The RAG side runs on the OpenAI API
  (`gpt-6-luna`); the baseline is the sub2api gateway (`codex/gpt-6-luna`), standing in for a
  general chatbot as people use it. Its Codex backend searches the web: in the first eval runs
  (when the gateway was also the RAG model) its session logs in `~/.codex/sessions/` showed web
  searches in 50 of 101 baseline sessions and none in RAG-answer or judge sessions. So the
  comparison is "RAG vs. a chatbot that may search the web", not the brief's "same model without
  retrieval". Unset `EVAL_BASELINE_*` to get that variant.
- **The judge is `claude-code/claude-haiku-5-5` on the sub2api gateway** (`EVAL_JUDGE_*`), another
  model family than the RAG model (`gpt-6-luna`), so it has no reason to favor RAG answers, and
  fast and cheap enough to run often. A small model is likelier to miss whether an answer states
  a key fact or only touches its topic, so `make eval-agreement` on human labels should confirm
  it against `claude-code/claude-opus-5-5`, which judged the runs before it. It runs through
  Claude Code (`claude --print`, no tools), not the raw Anthropic API, and subscription use is
  personal only. Runs judged by another model are not directly comparable.
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

- **Golden set review.** All 50 questions and their key facts were drafted from the corpus and
  carry `needs_review: true`. A domain expert should review them before thresholds are raised.
- **Follow-up questions** reuse the IDs of the previous question when they name none; there is no
  LLM query rewrite yet.
- **English questions about German-only text.** KI-MIG exists only in German, and English
  questions about it ("which authority is the market surveillance authority under the KI-MIG?")
  often miss it: the AI Act's English articles on market surveillance outrank it. Questions that
  cite a section (`§ 2 KI-MIG`) are found by ID. A query translation step or a source filter
  when a question names the KI-MIG would fix it.
- **The reranker floor (`RERANK_MIN_SCORE=0`) was calibrated on the golden set** (off-topic
  questions top out near -1, answerable ones start above 1). That is the set it is evaluated on,
  so the abstention numbers are optimistic until it is checked on held-out questions.
- **Language detection** is a small EN/DE word-list heuristic; very short or mixed questions can
  be misclassified, which affects only the footer language and which legal-text language is
  preferred.
- **Local models on CPU.** The reranker dominates latency on CPU. The machine has a GPU;
  `fastembed-gpu` would cut it, at the cost of a CUDA runtime dependency.
