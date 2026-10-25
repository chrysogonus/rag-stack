"""Deterministic additions to every answer: sources with attribution, versions, AI label."""

import re
from collections.abc import Sequence

from rag_stack.agent.prompts import ABSTAIN
from rag_stack.ingestion.models import Chunk
from rag_stack.retrieval.index import catalog_label

LABELS = {
    "en": {
        "sources": "Sources",
        "retrieved": "Retrieved sources (none cited)",
        "versions": "Source versions",
        "indexed": "The knowledge base covers",
        "hint": "Try naming what you're asking about: a technique ID such as AML.T0051, an OWASP "
        "entry such as LLM01, or an AI Act article such as Article 50.",
        "ai": "*AI-generated answer (EU AI Act Art. 50(1)). Check the cited sources.*",
    },
    "de": {
        "sources": "Quellen",
        "retrieved": "Abgerufene Quellen (keine zitiert)",
        "versions": "Quellenversionen",
        "indexed": "Die Wissensbasis umfasst",
        "hint": "Nennen Sie am besten, worum es geht: eine Technik-ID wie AML.T0051, einen "
        "OWASP-Eintrag wie LLM01 oder einen Artikel der KI-VO wie Art. 50.",
        "ai": "*KI-generierte Antwort (Art. 50 Abs. 1 KI-VO). Bitte prüfen Sie die Quellen.*",
    },
}
FOOTER_START = "\n\n---\n**"
BRACKETED = re.compile(r"\[([^\[\]\n]{2,80})\]")


LINK = re.compile(r"\[([^\[\]\n]{1,200})\]\((\S+?)\)")


def cited_ids(answer: str, sources: Sequence[Chunk]) -> list[str]:
    """Source IDs the answer cites, in order: as [ID], [ID](url) or [any text](source url).

    A link's text wins over its URL, and a URL counts only when one source has it: all
    paragraphs of an article share the article's URL."""
    known = {c.native_id for c in sources}
    urls: dict[str, set[str]] = {}
    for c in sources:
        urls.setdefault(c.url, set()).add(c.native_id)
    found = [
        (m.start(), part.strip())
        for m in BRACKETED.finditer(answer)
        for part in re.split(r"[,;]", m.group(1))
        if part.strip() in known
    ]
    for m in LINK.finditer(answer):
        named = any(part.strip() in known for part in re.split(r"[,;]", m.group(1)))
        owners = urls.get(m.group(2), set())
        if not named and len(owners) == 1:
            found.append((m.start(), next(iter(owners))))
    return list(dict.fromkeys(i for _, i in sorted(found)))


def is_abstention(answer: str) -> bool:
    return answer.strip().startswith(ABSTAIN)


def footer(answer: str, sources: Sequence[Chunk], language: str) -> str:
    labels = LABELS[language]
    by_id = {}
    for chunk in sources:
        by_id.setdefault(chunk.native_id, chunk)
    cited = cited_ids(answer, sources)
    listed = [by_id[i] for i in cited] or list(by_id.values())
    lines = [
        f"- [{c.native_id}]({c.url}) {c.title}. {c.attribution}"
        + ("" if c.license in c.attribution else f" ({c.license})")
        for c in listed
    ]
    versions = "; ".join(dict.fromkeys(catalog_label(c) for c in listed))
    heading = labels["sources"] if cited else labels["retrieved"]
    return (
        f"{FOOTER_START}{heading}**\n\n"
        + "\n".join(lines)
        + f"\n\n{labels['versions']}: {versions}\n\n{labels['ai']}"
    )


def abstention(catalog: Sequence[str], language: str) -> str:
    """The refusal (exactly `ABSTAIN` first: evals key on it), a hint and the source names."""
    labels = LABELS[language]
    indexed = "\n".join(f"- {name}" for name in catalog)
    return f"{ABSTAIN}\n\n{labels['hint']}\n\n{labels['indexed']}:\n\n{indexed}\n\n{labels['ai']}"
