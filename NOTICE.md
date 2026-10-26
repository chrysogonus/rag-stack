# Notices for third-party content

This project ingests the sources below into a local index (`data/`, not committed) and quotes
them in answers. Every chunk stores its license and attribution, and every answer lists the
attribution of each cited source. Small verbatim excerpts are committed as test fixtures in
`tests/fixtures/`, under the same terms.

| Source | License | Required notice |
|---|---|---|
| MITRE ATLAS™ (`atlas-data`) | Apache License 2.0 | "MITRE ATLAS™, Copyright 2021-2026 MITRE". Licensed under the Apache License, Version 2.0, https://www.apache.org/licenses/LICENSE-2.0. ATLAS and MITRE ATLAS are trademarks of The MITRE Corporation. |
| OWASP Top 10 for LLM Applications 2026 (OWASP GenAI Security Project) | CC BY-SA 4.0 | "OWASP Top 10 for LLM Applications 2026", OWASP GenAI Security Project, https://github.com/GenAI-Security-Project/GenAI-LLM-Top10, CC BY-SA 4.0. Excerpts and derived chunks are shared under the same license. |
| OWASP Top 10 for Agentic Applications for 2026 (OWASP GenAI Security Project) | CC BY-SA 4.0 | "OWASP Top 10 for Agentic Applications for 2026", OWASP GenAI Security Project, https://genai.owasp.org, CC BY-SA 4.0. Excerpts and derived chunks are shared under the same license. |
| Regulation (EU) 2024/1689 (AI Act), EN and DE | Reuse under Commission Decision 2011/833/EU (`LicenseRef-EU-Decision-2011-833`) | "© European Union, https://eur-lex.europa.eu". Only the Official Journal text is authentic; consolidated versions are documentation. |
| KI-Marktüberwachungs- und Innovationsförderungsgesetz (KI-MIG), BGBl. 2026 I Nr. 223 | Official work, no copyright (§ 5 UrhG, `LicenseRef-UrhG-5`) | Source: https://www.gesetze-im-internet.de/ki-mig/ (Federal Ministry of Justice). |
| GitHub Advisory Database, via OSV | CC BY 4.0 | "GitHub Advisory Database", https://github.com/github/advisory-database, CC BY 4.0. PyPA advisory records (PYSEC) are CC BY 4.0 as well. |
| NVD (NIST National Vulnerability Database) | Public domain (`LicenseRef-NVD-Public-Domain`) | "This product uses the NVD API but is not endorsed or certified by the NVD." |
| CISA Known Exploited Vulnerabilities catalog | CC0 1.0 | None required; credited as CISA KEV. |

The open-weights models used at runtime (`intfloat/multilingual-e5-large`, MIT;
`BAAI/bge-reranker-v2-m3` (int8 build), Apache-2.0; `Qdrant/bm25`; with the `gpu` profile
`Qwen/Qwen3-Embedding-4B` and `Qwen/Qwen3-Reranker-0.6B`, Apache-2.0) are downloaded on first use
and are not redistributed here. `deploy/vllm/qwen3_reranker.jinja` is adapted from vLLM's
example template (Apache-2.0).
