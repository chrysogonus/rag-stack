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
            "vulns",
            "Vulnerabilities (CISA KEV, GitHub Advisory Database, NVD, EPSS)",
            "CC-BY-4.0",
            "GitHub Advisory Database (CC BY 4.0), also via OSV; NVD (public domain); "
            "CISA KEV (CC0); EPSS by FIRST",
            "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        ),
        SourceInfo(
            "attack",
            "MITRE ATT&CK",
            "LicenseRef-MITRE-ATTACK-Terms",
            "© 2026 The MITRE Corporation. This work is reproduced and distributed with the "
            "permission of The MITRE Corporation.",
            "https://attack.mitre.org",
        ),
        SourceInfo(
            "capec",
            "MITRE CAPEC",
            "LicenseRef-MITRE-CAPEC-Terms",
            "CAPEC™, Copyright © 2007–2026, The MITRE Corporation",
            "https://capec.mitre.org",
        ),
        SourceInfo(
            "cwe",
            "MITRE CWE",
            "LicenseRef-MITRE-CWE-Terms",
            "CWE™, Copyright © 2006–2026, The MITRE Corporation",
            "https://cwe.mitre.org",
        ),
        SourceInfo(
            "d3fend",
            "MITRE D3FEND",
            "LicenseRef-MITRE-D3FEND-Terms",
            "D3FEND™, © 2025 The MITRE Corporation",
            "https://d3fend.mitre.org",
        ),
    ]
}

# Laws by source, for their parsers and for finding references to them in questions: the short
# name their unit IDs start with ("AI Act Art. 50(1)", "KI-MIG § 2"), then a regex of the names
# a question may use (case-insensitive).
EU_ACTS: dict[str, tuple[str, str]] = {
    "eu-ai-act": ("AI Act", r"AI Act|AI Regulation|KI-VO|KI-Verordnung|2024/1689"),
}
GERMAN_LAWS: dict[str, tuple[str, str]] = {
    "ki-mig": ("KI-MIG", r"KI-MIG|KI-Marktüberwachungs\w*"),
}


def eu_id(act: str, unit: str) -> str:
    """Native ID of a unit of an EU act: 'Art. 50(1)', 'Recital 133', 'Annex III 1(a)'."""
    # The AI Act's recitals and annexes keep their IDs from when it was the only act indexed.
    return unit if act == "AI Act" and not unit.startswith("Art.") else f"{act} {unit}"
