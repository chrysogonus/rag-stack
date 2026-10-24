from dataclasses import dataclass


@dataclass(frozen=True)
class SourceInfo:
    id: str
    name: str
    license: str
    attribution: str
    url: str


# License ids are SPDX where one exists, LicenseRef-* otherwise (see NOTICE.md).
SOURCES: dict[str, SourceInfo] = {
    s.id: s
    for s in [
        SourceInfo(
            "atlas",
            "MITRE ATLAS",
            "Apache-2.0",
            "MITRE ATLAS™, Copyright 2021-2026 MITRE, Apache-2.0",
            "https://atlas.mitre.org",
        ),
        SourceInfo(
            "owasp-llm-2026",
            "OWASP Top 10 for LLM Applications 2026",
            "CC-BY-SA-4.0",
            "OWASP GenAI Security Project, OWASP Top 10 for LLM Applications 2026, CC BY-SA 4.0",
            "https://github.com/GenAI-Security-Project/GenAI-LLM-Top10",
        ),
        SourceInfo(
            "owasp-agentic-2026",
            "OWASP Top 10 for Agentic Applications 2026",
            "CC-BY-SA-4.0",
            "OWASP GenAI Security Project, OWASP Top 10 for Agentic Applications for 2026, "
            "CC BY-SA 4.0",
            "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/",
        ),
        SourceInfo(
            "eu-ai-act",
            "EU AI Act (Regulation (EU) 2024/1689)",
            "LicenseRef-EU-Decision-2011-833",
            "© European Union, https://eur-lex.europa.eu",
            "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        ),
        SourceInfo(
            "ki-mig",
            "KI-MIG (KI-Marktüberwachungs- und Innovationsförderungsgesetz)",
            "LicenseRef-UrhG-5",
            "Amtliches Werk (§ 5 UrhG), Quelle: https://www.gesetze-im-internet.de/ki-mig/",
            "https://www.gesetze-im-internet.de/ki-mig/",
        ),
        SourceInfo(
            "ai-vulns",
            "AI package vulnerabilities (NVD, GitHub Advisory Database via OSV, CISA KEV)",
            "CC-BY-4.0",
            "GitHub Advisory Database (CC BY 4.0) via OSV; NVD (public domain); CISA KEV (CC0)",
            "https://osv.dev",
        ),
    ]
}
