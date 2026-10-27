import re
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["capec"]
SITE = "https://capec.mitre.org/data/definitions"
RETIRED = {"Deprecated", "Obsolete"}
BLOCKS = {"p", "li", "div", "tr"}


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    # Versioned catalogs never change once released: the version in the config pins them.
    version = str(config["version"])
    name = f"capec_v{version}.xml"
    url = f"{config['base_url']}/{name}"
    xml = fetcher.get(url)
    catalog = BeautifulSoup(xml, "lxml-xml").find("Attack_Pattern_Catalog")
    if not isinstance(catalog, Tag) or catalog.get("Version") != version:
        raise ValueError(f"{url}: not the CAPEC {version} catalog")
    return Snapshot(INFO.id, version, retrieved_at, {name: xml}, {name: url})


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    (xml,) = snapshot.files.values()
    chunks = []
    edges = []
    for ap in BeautifulSoup(xml, "lxml-xml").find_all("Attack_Pattern"):
        if ap["Status"] in RETIRED:
            continue
        native_id = f"CAPEC-{ap['ID']}"
        rating = [
            f"{label}: {value}"
            for label, tag in [
                ("Likelihood of attack", "Likelihood_Of_Attack"),
                ("Typical severity", "Typical_Severity"),
            ]
            if (value := text(ap.find(tag)))
        ]
        sections = [
            f"{ap['Name']} (attack pattern, {str(ap['Abstraction']).lower()})",
            text(ap.find("Description", recursive=False)),
            text(ap.find("Extended_Description")),
            "\n".join(rating),
            listed("Prerequisites", ap.find_all("Prerequisite")),
            listed("Execution flow", [step(s) for s in ap.find_all("Attack_Step")]),
            listed("Skills required", [f"{s['Level']}: {text(s)}" for s in ap.find_all("Skill")]),
            listed("Resources required", ap.find_all("Resource")),
            listed("Indicators", ap.find_all("Indicator")),
            listed("Consequences", [consequence(c) for c in ap.find_all("Consequence")]),
            listed("Mitigations", ap.find_all("Mitigation")),
            listed("Example instances", ap.find_all("Example")),
        ]
        chunks.append(
            Chunk(
                source_id=INFO.id,
                native_id=native_id,
                title=str(ap["Name"]),
                url=f"{SITE}/{ap['ID']}.html",
                source_version=snapshot.version,
                language="en",
                retrieved_at=snapshot.retrieved_at,
                license=INFO.license,
                attribution=INFO.attribution,
                text="\n\n".join(s for s in sections if s),
                heading_path=["attack pattern"],
                meta={
                    "kind": "attack pattern",
                    "abstraction": ap["Abstraction"],
                    "status": ap["Status"],
                },
            )
        )
        # "ChildOf" -> "child_of", like the other sources' relation names.
        edges += [
            Edge(
                src_id=native_id,
                rel=re.sub(r"(?<!^)(?=[A-Z])", "_", str(r["Nature"])).lower(),
                dst_id=f"CAPEC-{r['CAPEC_ID']}",
                origin=INFO.id,
            )
            for r in ap.find_all("Related_Attack_Pattern")
        ]
        edges += [
            Edge(
                src_id=native_id,
                rel="related_weakness",
                dst_id=f"CWE-{w['CWE_ID']}",
                origin=INFO.id,
            )
            for w in ap.find_all("Related_Weakness")
        ]
        edges += [
            Edge(
                src_id=native_id,
                rel="maps_to",
                dst_id=f"T{text(m.find('Entry_ID'))}",
                origin=INFO.id,
            )
            for m in ap.find_all("Taxonomy_Mapping", Taxonomy_Name="ATTACK")
        ]
    return chunks, edges


def text(el: Any) -> str:
    """An element's text with its XHTML markup (paragraphs, lists) flattened; '' if missing."""
    if not isinstance(el, Tag):
        return ""
    return clean(re.sub(r"\s*\n\s*", "\n", "".join(lines(el))))


def lines(el: Tag) -> Iterator[str]:
    """The file's line breaks only wrap the XML; block elements and <br/> (in commands and HTTP
    exchanges) break lines."""
    for child in el.children:
        if isinstance(child, Tag):
            block = child.name in BLOCKS
            yield "\n" if block or child.name == "br" else ""
            yield from lines(child)
            yield "\n" if block else ""
        elif isinstance(child, NavigableString) and not isinstance(child, Comment):
            yield re.sub(r"\s+", " ", child)


def listed(heading: str, items: list[Any]) -> str:
    lines = [
        f"- {line}" for item in items if (line := item if isinstance(item, str) else text(item))
    ]
    return f"{heading}:\n" + "\n".join(lines) if lines else ""


def step(el: Tag) -> str:
    """'1. Explore: [Survey application] ...'. Its techniques are tool-level detail and stay out."""
    return f"{text(el.find('Step'))}. {text(el.find('Phase'))}: {text(el.find('Description'))}"


def consequence(el: Tag) -> str:
    """'Confidentiality, Integrity: Read Data, Modify Data (note)'."""
    scopes = ", ".join(text(s) for s in el.find_all("Scope"))
    impacts = ", ".join(text(i) for i in el.find_all("Impact"))
    note = f" ({text(el.find('Note'))})" if el.find("Note") else ""
    return f"{scopes}: {impacts}{note}"
