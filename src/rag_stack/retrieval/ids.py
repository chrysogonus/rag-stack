"""Find citable unit IDs in a question and normalize them to the index's native IDs."""

import re

from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS, eu_id

GERMAN_NAMES = "|".join(names for _, names in GERMAN_LAWS.values())
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bAML\.(TA\d{4}|T\d{4}(?:\.\d{3})?|M\d{4}|CS\d{4})\b", re.I), "atlas"),
    (re.compile(r"\bLLM\s?(\d{2})(?::(\d{4}))?\b", re.I), "owasp-llm"),
    (re.compile(r"\bASI\s?(\d{2})\b", re.I), "asi"),
    (re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.I), "cve"),
    (re.compile(r"\bGHSA(?:-[23456789cfghjmpqrvwx]{4}){3}\b", re.I), "ghsa"),
    # "Article 50(1)", "Art. 50 Abs. 1", "Artikel 50 Absatz 1", "Art. 4a"
    (
        re.compile(
            r"\bArt(?:icle|ikel|\.)?\s*(\d+[a-z]?)\b(?:\s*\((\d+[a-z]?)\)|\s+(?:Abs\.|Absatz)\s*(\d+[a-z]?))?",
            re.I,
        ),
        "article",
    ),
    # "paragraph 1 of Article 50"
    (re.compile(r"\bparagraph\s+(\d+[a-z]?)\s+of\s+Article\s+(\d+[a-z]?)\b", re.I), "paragraph"),
    (re.compile(r"\b(?:Recital|Erwägungsgrund)\s+(\d+)\b", re.I), "recital"),
    # "Annex III", "Annex III point 1(a)", "Anhang III Nummer 1 Buchstabe a"
    (
        re.compile(
            r"\b(?:Annex|Anhang)\s+([IVXL]+)\b(?:\s*(?:point|Nummer|Nr\.)?\s*(\d+)"
            r"(?:\s*(?:\(([a-z])\)|Buchstabe\s+([a-z])\b))?)?",
        ),
        "annex",
    ),
    # "§ 2 Abs. 1", "§ 3 KI-MIG", "Section 3(1) KI-MIG" ("Section" alone also names annex parts)
    (
        re.compile(
            rf"(?:§\s*(\d+[a-z]?)|\bSection\s+(\d+[a-z]?)(?=[^.]{{0,20}}(?:{GERMAN_NAMES})))"
            r"(?:\s*(?:Abs\.|Absatz)\s*(\d+[a-z]?)|\s*\((\d+)\))?",
            re.I,
        ),
        "section",
    ),
    # ATT&CK: tactics, (sub-)techniques, detection strategies, mitigations, groups, software,
    # campaigns. Not inside an ATLAS ID (AML.T0051).
    # shortcut: product names match too ("M1000", and "A10" below); a missing ID finds nothing,
    # but stops a follow-up from reusing the previous question's IDs. Require context if it bites.
    (re.compile(r"(?<![\w.])((?i:TA|T)\d{4}(?:\.\d{3})?|DET\d{4}|[MGSC]\d{4})\b"), "upper"),
    (re.compile(r"\b(CWE|CAPEC)[-\s]?(\d{1,5})\b", re.I), "mitre-list"),
    (re.compile(r"\bD3-[A-Z]{2,}\b", re.I), "upper"),
    # NIST CSF 2.0 "PR.AA-01", SP 800-53 "AC-2(1)", SSDF "PO.1.1", AI RMF "GOVERN 1.1"
    (re.compile(r"\b(?:GV|ID|PR|DE|RS|RC)\.[A-Z]{2}(?:-\d{2})?\b"), "same"),
    (
        re.compile(
            r"\b((?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)-\d{1,2})"
            r"(?:\s?\((\d{1,2})\))?(?![\d-])"
        ),
        "sp800-53",
    ),
    (re.compile(r"\b(?:SSDF\s+)?((?:PO|PS|PW|RV)\.\d+(?:\.\d+)?)\b"), "ssdf"),
    (re.compile(r"\b(?:AI RMF\s+)?(GOVERN|MAP|MEASURE|MANAGE)\s+(\d+(?:\.\d+)?)\b"), "ai-rmf"),
    # OWASP Top 10 "A01:2025", ASVS 5.0 "v5.0.0-1.2.5" (also "ASVS 1.2.5", "ASVS V1.2.5")
    (re.compile(r"\bA(\d{2})(?::(\d{4}))?\b"), "owasp-top10"),
    (re.compile(r"\b(?:v5\.0\.0-|ASVS\s+(?:5\.0\s+)?V?)(\d+\.\d+\.\d+)\b", re.I), "asvs"),
    (re.compile(r"\barXiv(?::\s?|\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5})", re.I), "arxiv"),
]


def detect_ids(text: str) -> list[str]:
    """Native IDs (or the parent IDs of whole articles, annexes and sections) in text."""
    found: list[str] = []
    for pattern, kind in PATTERNS:
        for m in pattern.finditer(text):
            found.extend(normalize(kind, m, text))
    found = list(dict.fromkeys(found))
    # "paragraph 1 of Article 50" also matches "Article 50": keep only the specific unit.
    return [i for i in found if not any(o != i and o.startswith((f"{i}(", f"{i} ")) for o in found)]


def acts(laws: dict[str, tuple[str, str]], text: str, m: re.Match[str]) -> list[str]:
    """Short names of the acts a legal reference may be to: the one named nearest to it in the
    text ("Art. 21 NIS2", "AI Act Article 50"), or, with none named, every indexed act."""
    start, end = m.span()
    named = [
        (max(n.start() - end, start - n.end(), 0), short)
        for short, names in laws.values()
        for n in re.finditer(rf"\b(?:{names})\b", text, re.I)
    ]
    return [min(named)[1]] if named else [short for short, _ in laws.values()]


def normalize(kind: str, m: re.Match[str], text: str) -> list[str]:
    if kind == "atlas":
        return [f"AML.{m.group(1).upper()}"]
    if kind == "owasp-llm":
        year = m.group(2)
        return [f"LLM{m.group(1)}:2026"] if year in (None, "2026") else []
    if kind == "asi":
        return [f"ASI{m.group(1)}"]
    if kind in ("cve", "ghsa"):
        return [m.group(0).upper() if kind == "cve" else "GHSA" + m.group(0)[4:].lower()]
    if kind == "article":
        number, paragraph = m.group(1), m.group(2) or m.group(3)
        unit = f"Art. {number}" + (f"({paragraph})" if paragraph else "")
        return [eu_id(act, unit) for act in acts(EU_ACTS, text, m)]
    if kind == "paragraph":
        return [eu_id(act, f"Art. {m.group(2)}({m.group(1)})") for act in acts(EU_ACTS, text, m)]
    if kind == "recital":
        return [eu_id(act, f"Recital {m.group(1)}") for act in acts(EU_ACTS, text, m)]
    if kind == "annex":
        annex, point, letter = m.group(1), m.group(2), m.group(3) or m.group(4)
        unit = f"Annex {annex}"
        if point:
            unit += f" {point}" + (f"({letter})" if letter else "")
        return [eu_id(act, unit) for act in acts(EU_ACTS, text, m)]
    if kind == "section":
        section, paragraph = m.group(1) or m.group(2), m.group(3) or m.group(4)
        unit = f"§ {section}" + (f" Abs. {paragraph}" if paragraph else "")
        return [f"{law} {unit}" for law in acts(GERMAN_LAWS, text, m)]
    if kind == "upper":
        return [m.group(0).upper()]
    if kind == "same":
        return [m.group(0)]
    if kind == "mitre-list":
        return [f"{m.group(1).upper()}-{m.group(2)}"]
    if kind == "sp800-53":
        return [m.group(1) + (f"({m.group(2)})" if m.group(2) else "")]
    if kind == "ssdf":
        return [f"SSDF {m.group(1)}"]
    if kind == "ai-rmf":
        return [f"AI RMF {m.group(1)} {m.group(2)}"]
    if kind == "owasp-top10":
        return [f"A{m.group(1)}:2025"] if m.group(2) in (None, "2025") else []
    if kind == "asvs":
        return [f"v5.0.0-{m.group(1)}"]
    return [f"arXiv:{m.group(1)}"]
