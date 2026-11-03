"""Deterministic additions to every answer: sources with attribution, versions, AI label."""

import re
from collections.abc import Sequence

from rag_stack.agent.prompts import ABSTAIN
from rag_stack.ingestion.models import Chunk
from rag_stack.pack import Pack
from rag_stack.retrieval.index import catalog_label

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


def footer(answer: str, sources: Sequence[Chunk], pack: Pack, language: str) -> str:
    text = pack.labels[language]
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
    versions = "; ".join(dict.fromkeys(catalog_label(c, pack.sources) for c in listed))
    heading = text["sources"] if cited else text["retrieved"]
    return (
        f"{FOOTER_START}{heading}**\n\n"
        + "\n".join(lines)
        + f"\n\n{text['versions']}: {versions}\n\n{text['ai']}"
    )


def abstention(catalog: Sequence[str], pack: Pack, language: str) -> str:
    """The refusal (exactly `ABSTAIN` first: evals key on it), a hint and the source names."""
    text = pack.labels[language]
    indexed = "\n".join(f"- {name}" for name in catalog)
    return f"{ABSTAIN}\n\n{text['hint']}\n\n{text['indexed']}:\n\n{indexed}\n\n{text['ai']}"
