"""EU acts from CELLAR, configured by CELEX number (config/sources.yaml) and short name
(registry.EU_ACTS)."""

import copy
import json
import re
import warnings
from typing import Any

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
from bs4.element import NavigableString

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import EU_ACTS, SOURCES, eu_id

BLOCKS = {"p", "div", "table", "tbody", "li", "ul", "ol", "br", "hr"}
CONSOLIDATED = """\
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex WHERE {{ ?w cdm:resource_legal_id_celex ?celex .
  FILTER(STRSTARTS(STR(?celex), "{prefix}")) }}"""


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    """Articles and annexes come from the latest consolidated version (which drops the
    recitals), recitals from the act as published in the Official Journal."""
    celex = config["celex"]
    found = json.loads(
        fetcher.get(
            config["sparql_url"],
            params={
                "query": CONSOLIDATED.format(prefix="0" + celex[1:]),
                "format": "application/sparql-results+json",
            },
        )
    )
    versions = sorted(b["celex"]["value"] for b in found["results"]["bindings"])
    consolidated = versions[-1] if versions else celex
    files, urls = {}, {}
    for lang, code in config["languages"].items():
        for kind, doc in (("consolidated", consolidated), ("oj", celex)):
            name = f"{kind}_{lang}.xhtml"
            files[name] = fetcher.get(
                config["resource_url"] + doc,
                headers={"Accept": "application/xhtml+xml", "Accept-Language": code},
            )
            urls[name] = (
                f"https://eur-lex.europa.eu/legal-content/{lang.upper()}/TXT/HTML/?uri=CELEX:{doc}"
            )
    return Snapshot(config["id"], consolidated, retrieved_at, files, urls)


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    info, act = SOURCES[snapshot.source_id], EU_ACTS[snapshot.source_id][0]
    # The version is a CELEX number, of the act ("32024R1689") or a consolidation ("02024R1689-…").
    oj = f"OJ {snapshot.version[1:5]}/{int(snapshot.version[6:10])}"
    chunks: list[Chunk] = []
    for name, raw in snapshot.files.items():
        kind, lang = name.removesuffix(".xhtml").split("_")
        with warnings.catch_warnings():
            # The documents are XHTML; the HTML parser handles them and their entities best.
            warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
            soup = BeautifulSoup(raw, "lxml")
        for marker in soup.select("p.modref, p.arrow"):
            marker.decompose()

        units = recitals(soup, act) if kind == "oj" else [*articles(soup, act), *annexes(soup, act)]
        for native_id, title, text, anchor, unit_key, parents in units:
            chunks.append(
                Chunk(
                    source_id=info.id,
                    native_id=native_id,
                    title=clean(title),
                    url=f"{snapshot.urls[name]}#{anchor}",
                    source_version=snapshot.version if kind == "consolidated" else oj,
                    language=lang,
                    retrieved_at=snapshot.retrieved_at,
                    license=info.license,
                    attribution=info.attribution,
                    text=clean(text),
                    unit_key=unit_key,
                    parent_ids=parents,
                )
            )
    return [c for c in chunks if c.text], []


def number(label: str) -> str:
    """'1.', '(1)', 'a)', '(a)' -> '1', '1', 'a', 'a'."""
    return label.strip().strip("().").strip()


def is_point(label: Tag | None) -> bool:
    """A paragraph or point label of the act itself: not a dash bullet, and not a label quoted
    from the act an amending article inserts it into ('5., „(5))."""
    return label is not None and bool(re.fullmatch(r"\d+[a-z]?|[a-z]+", number(label.get_text())))


def classes(el: Tag) -> list[str]:
    return list(el.get_attribute_list("class"))


def element_id(el: Tag) -> str:
    return str(el["id"])


def block_text(el: Tag) -> str:
    """Text with a line break per block element, and list labels kept on their item's line."""
    parts = []
    for child in el.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif not isinstance(child, Tag):
            continue
        elif child.name == "tr":
            parts.append(
                "\n" + " ".join(block_text(td).strip() for td in child.find_all("td")) + "\n"
            )
        elif "grid-list-column-1" in classes(child):
            parts.append("\n" + child.get_text(strip=True) + " ")
        elif "grid-list-column-2" in classes(child):
            parts.append(block_text(child).strip() + "\n")
        elif child.name in BLOCKS:
            parts.append("\n" + block_text(child) + "\n")
        else:
            parts.append(block_text(child))
    return "".join(parts)


def items(el: Tag) -> list[tuple[str, Tag]]:
    """Top-level list items of a consolidated-text element: (label, content column)."""
    found = []
    for grid in el.select("div.grid-container"):
        enclosing = grid.find_parent("div", class_="grid-container")
        if enclosing is not None and any(p is el for p in enclosing.parents):
            continue  # nested inside another item of el
        label = grid.find("div", class_="grid-list-column-1", recursive=False)
        content = grid.find("div", class_="grid-list-column-2", recursive=False)
        if label and content and is_point(label):
            found.append((number(label.get_text()), content))
    return found


def without_lists(el: Tag) -> str:
    stripped = copy.copy(el)
    for grid in stripped.select("div.grid-container"):
        if is_point(grid.find("div", class_="grid-list-column-1", recursive=False)):
            grid.decompose()
    return block_text(stripped)


def articles(soup: BeautifulSoup, act: str):
    for art in soup.find_all("div", id=re.compile(r"^art_\d+[a-z]?$")):
        n = element_id(art).removeprefix("art_")
        title = " ".join(
            h.get_text(" ", strip=True)
            for h in art.select("p.title-article-norm, p.stitle-article-norm")
        )
        base = eu_id(act, f"Art. {n}")
        paragraphs = [
            d
            for d in art.find_all("div", class_="norm", recursive=False)
            if is_point(d.find("span", class_="no-parag", recursive=False))
        ]
        if paragraphs:
            for para in paragraphs:
                label = para.find("span", class_="no-parag", recursive=False)
                if label is None:
                    continue
                p = number(label.get_text())
                label.extract()
                # A paragraph's further subparagraphs follow its div as siblings, up to the next.
                blocks = [para]
                for sibling in para.find_next_siblings():
                    if any(sibling is d for d in paragraphs):
                        break
                    blocks.append(sibling)
                yield (
                    f"{base}({p})",
                    title,
                    "\n".join(block_text(b) for b in blocks),
                    element_id(art),
                    f"{element_id(art)}.{p}",
                    [base],
                )
            continue
        body = copy.copy(art)
        for heading in body.select("p.title-article-norm, div.eli-title"):
            heading.decompose()
        points = items(body)
        if not points:
            yield base, title, block_text(body), element_id(art), element_id(art), []
            continue
        yield base, title, without_lists(body), element_id(art), element_id(art), []
        for p, content in points:
            yield (
                f"{base}({p})",
                title,
                f"({p}) " + block_text(content).strip(),
                element_id(art),
                f"{element_id(art)}.{p}",
                [base],
            )


def annexes(soup: BeautifulSoup, act: str):
    for annex in soup.find_all("div", id=re.compile(r"^anx_[IVXL]+$")):
        n = element_id(annex).removeprefix("anx_")
        headings = annex.select("p.title-annex-1, p.title-annex-2")
        title = " ".join(h.get_text(" ", strip=True) for h in headings)
        body = copy.copy(annex)
        for heading in body.select("p.title-annex-1, p.title-annex-2"):
            heading.decompose()
        base = eu_id(act, f"Annex {n}")
        yield base, title, without_lists(body), element_id(annex), element_id(annex), []
        for p, content in items(body):
            point = f"{base} {p}"
            key = f"{annex['id']}.{p}"
            yield (
                point,
                title,
                f"{p}. " + without_lists(content).strip(),
                element_id(annex),
                key,
                [base],
            )
            for letter, sub in items(content):
                yield (
                    f"{point}({letter})",
                    title,
                    f"({letter}) " + block_text(sub).strip(),
                    element_id(annex),
                    f"{key}.{letter}",
                    [base, point],
                )


def recitals(soup: BeautifulSoup, act: str):
    for recital in soup.find_all("div", id=re.compile(r"^rct_\d+$")):
        n = element_id(recital).removeprefix("rct_")
        cells = recital.find_all("td")
        text = block_text(cells[-1]) if cells else block_text(recital)
        yield (
            eu_id(act, f"Recital {n}"),
            f"Recital {n}",
            text,
            element_id(recital),
            element_id(recital),
            [],
        )
