"""German federal laws from gesetze-im-internet.de, by short name (registry.GERMAN_LAWS)."""

import io
import re
import zipfile
from typing import Any

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import GERMAN_LAWS, SOURCES
from rag_stack.retrieval.ids import detect_ids

# "Artikel 30 Absatz 2 der Verordnung (EU) 2024/1689", "des Anhangs III Nummer 2 der Verordnung ..."
AI_ACT_CITATION = re.compile(
    r"\b(?:Artikels?|Art\.|Anhangs?|Anhänge|Anhängen)\s[^;()]{0,80}?Verordnung \(EU\) 2024/1689"
)


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    """Official XML of the law from gesetze-im-internet.de (Federal Ministry of Justice)."""
    archive = zipfile.ZipFile(io.BytesIO(fetcher.get(config["xml_url"])))
    xml_name = next(n for n in archive.namelist() if n.endswith(".xml"))
    xml = archive.read(xml_name)
    build = BeautifulSoup(xml, "lxml-xml").find("dokumente")
    if build is None:
        raise ValueError(f"{config['xml_url']}: not a gesetze-im-internet.de document")
    name = f"{config['id']}.xml"
    return Snapshot(
        config["id"], str(build["builddate"]), retrieved_at, {name: xml}, {name: config["page_url"]}
    )


def text_of(el: Tag) -> str:
    """Numbered lists (<DT>1.</DT><DD>...</DD>) become one line per item."""
    parts = []
    for child in el.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag) and child.name == "DT":
            parts.append("\n" + child.get_text(strip=True) + " ")
        elif isinstance(child, Tag):
            parts.append(text_of(child))
    return "".join(parts)


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    info, law = SOURCES[snapshot.source_id], GERMAN_LAWS[snapshot.source_id][0]
    name = f"{snapshot.source_id}.xml"
    soup = BeautifulSoup(snapshot.files[name], "lxml-xml")
    fundstelle = soup.find("fundstelle")
    gazette = fundstelle.get_text(" ", strip=True) if fundstelle else ""
    version = f"{snapshot.version[:4]}-{snapshot.version[4:6]}-{snapshot.version[6:8]}"
    chunks, part = [], ""
    for norm in soup.find_all("norm"):
        unit = norm.find("gliederungseinheit")
        if unit:
            part = " ".join(
                found.get_text(strip=True)
                for tag in ("gliederungsbez", "gliederungstitel")
                if (found := unit.find(tag))
            )
            continue
        enbez = norm.find("enbez")
        if not enbez or not enbez.get_text().startswith("§"):
            continue
        section = enbez.get_text(strip=True).removeprefix("§").strip()
        titel = norm.find("titel")
        title = f"§ {section} " + (titel.get_text(strip=True) if titel else "")
        content = norm.select_one("text Content")
        if content is None:
            continue
        base = f"{law} § {section}"
        for p in content.find_all("P", recursive=False):
            body = clean(text_of(p))
            numbered = re.match(r"\((\d+[a-z]?)\)\s*", body)
            native_id = f"{base} Abs. {numbered.group(1)}" if numbered else base
            chunks.append(
                Chunk(
                    source_id=info.id,
                    native_id=native_id,
                    title=title.strip(),
                    url=f"{snapshot.urls[name]}__{section}.html",
                    source_version=f"Stand {version}, {gazette}".strip(", "),
                    language="de",
                    retrieved_at=snapshot.retrieved_at,
                    license=info.license,
                    attribution=info.attribution,
                    text=body,
                    heading_path=[part, title.strip()],
                    parent_ids=[base] if numbered else [],
                    unit_key=native_id,
                )
            )
    # A section citing a unit of the AI Act links to it. Only spans ending in the regulation's
    # number: the law also cites other laws' sections, which would resolve to wrong IDs.
    edges = {
        (c.native_id, ref): Edge(src_id=c.native_id, rel="refers_to", dst_id=ref, origin=info.id)
        for c in chunks
        for span in AI_ACT_CITATION.findall(c.text)
        for ref in detect_ids(span)
        if ref not in (c.native_id, *c.parent_ids)
    }
    return chunks, list(edges.values())
