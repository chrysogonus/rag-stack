# Appendix A: Related Framework Mappings

## OWASP Top 10 for Agentic Applications (ASI) — 2026 (announced 2025-12-09)

*Relocated verbatim from the 2026 entries; maps each LLM risk to the OWASP Top 10 for Agentic Applications (ASI) risks.*

| Risk | Element | Relevance |
|---|---|---|
| **LLM01** Prompt Injection | ● ASI01 — Agent Goal Hijack | Injected input overrides the system-prompt role/capability constraints, redirecting agent goals. |
|  | ● ASI02 — Tool Misuse & Exploitation | Injected input drives unauthorized tool invocation (the "lethal trifecta" conditions). |
|  | ● ASI03 — Identity & Privilege Abuse | Agent acts under the user's elevated credentials, performing actions the attacker could not. |
## MITRE CWE (Common Weakness Enumeration) — 4.20

*Each OWASP LLM Top 10 2026 entry maps to the CWE weaknesses that name its root cause, with primary CWEs capturing the definitional weakness and supporting CWEs the top contributing failure modes.*

| Risk | Element | Relevance |
|---|---|---|
| **LLM01** Prompt Injection | ● CWE-1427 Improper Neutralization of Input Used for LLM Prompting | Untrusted input from prompts, retrieved documents, tool output, or memory alters model behavior because the model draws no boundary between instructions and data, the definitional prompt-injection weakness. |
|  | ○ CWE-707 Improper Neutralization (Pillar) | The pillar-level root cause is a failure to separate and neutralize attacker instructions from data on a single token stream. |
|  | ○ CWE-349 Acceptance of Extraneous Untrusted Data With Trusted Data | Context-window pooling merges untrusted retrieved content and tool output with trusted instructions under no enforced trust boundary. |
