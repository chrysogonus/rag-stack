"""Find citable unit IDs in a question and normalize them to the index's native IDs."""

import re

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
            r"(?:§\s*(\d+[a-z]?)|\bSection\s+(\d+[a-z]?)(?=[^.]{0,20}KI-MIG))"
            r"(?:\s*(?:Abs\.|Absatz)\s*(\d+[a-z]?)|\s*\((\d+)\))?",
            re.I,
        ),
        "kimig",
    ),
]


def detect_ids(text: str) -> list[str]:
    """Native IDs (or the parent IDs of whole articles, annexes and sections) in text."""
    found: list[str] = []
    for pattern, kind in PATTERNS:
        for m in pattern.finditer(text):
            found.extend(normalize(kind, m))
    found = list(dict.fromkeys(found))
    # "paragraph 1 of Article 50" also matches "Article 50": keep only the specific unit.
    return [i for i in found if not any(o != i and o.startswith((f"{i}(", f"{i} ")) for o in found)]


def normalize(kind: str, m: re.Match[str]) -> list[str]:
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
        base = f"AI Act Art. {number}"
        return [f"{base}({paragraph})" if paragraph else base]
    if kind == "paragraph":
        return [f"AI Act Art. {m.group(2)}({m.group(1)})"]
    if kind == "recital":
        return [f"Recital {m.group(1)}"]
    if kind == "annex":
        annex, point, letter = m.group(1), m.group(2), m.group(3) or m.group(4)
        if not point:
            return [f"Annex {annex}"]
        return [f"Annex {annex} {point}" + (f"({letter})" if letter else "")]
    section, paragraph = m.group(1) or m.group(2), m.group(3) or m.group(4)
    base = f"KI-MIG § {section}"
    return [f"{base} Abs. {paragraph}" if paragraph else base]
