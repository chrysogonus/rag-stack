import io
import re
import zipfile
from typing import Any

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["ki-mig"]


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    """Official XML of the law from gesetze-im-internet.de (Federal Ministry of Justice)."""
    archive = zipfile.ZipFile(io.BytesIO(fetcher.get(config["xml_url"])))
    xml_name = next(n for n in archive.namelist() if n.endswith(".xml"))
    xml = archive.read(xml_name)
    build = BeautifulSoup(xml, "lxml-xml").find("dokumente")
    if build is None:
        raise ValueError(f"{config['xml_url']}: not a gesetze-im-internet.de document")
    return Snapshot(
        INFO.id,
        str(build["builddate"]),
        retrieved_at,
        {"ki-mig.xml": xml},
        {"ki-mig.xml": config["page_url"]},
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
    soup = BeautifulSoup(snapshot.files["ki-mig.xml"], "lxml-xml")
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
        base = f"KI-MIG § {section}"
        for p in content.find_all("P", recursive=False):
            body = clean(text_of(p))
            numbered = re.match(r"\((\d+[a-z]?)\)\s*", body)
            native_id = f"{base} Abs. {numbered.group(1)}" if numbered else base
            chunks.append(
                Chunk(
                    source_id=INFO.id,
                    native_id=native_id,
                    title=title.strip(),
                    url=f"https://www.gesetze-im-internet.de/ki-mig/__{section}.html",
                    source_version=f"Stand {version}, {gazette}".strip(", "),
                    language="de",
                    retrieved_at=snapshot.retrieved_at,
                    license=INFO.license,
                    attribution=INFO.attribution,
                    text=body,
                    heading_path=[part, title.strip()],
                    parent_ids=[base] if numbered else [],
                    unit_key=native_id,
                )
            )
    return chunks, []
