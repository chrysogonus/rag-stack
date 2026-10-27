import io
import re
import zipfile
from typing import Any

from bs4 import BeautifulSoup, Tag

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot
from rag_stack.ingestion.registry import SOURCES
from rag_stack.ingestion.sources.capec import consequence, listed, text

INFO = SOURCES["cwe"]
SITE = "https://cwe.mitre.org/data/definitions"
RETIRED = {"Deprecated", "Obsolete"}


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    # Versioned catalogs never change once released: the version in the config pins them.
    version = str(config["version"])
    name = f"cwec_v{version}.xml"
    url = f"{config['base_url']}/{name}.zip"
    xml = zipfile.ZipFile(io.BytesIO(fetcher.get(url))).read(name)
    catalog = BeautifulSoup(xml, "lxml-xml").find("Weakness_Catalog")
    if not isinstance(catalog, Tag) or catalog.get("Version") != version:
        raise ValueError(f"{url}: not the CWE {version} catalog")
    return Snapshot(INFO.id, version, retrieved_at, {name: xml}, {name: url})


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    """One chunk per weakness. Categories and views only group weaknesses and stay out, as do
    code examples. CAPEC links are stored by the CAPEC source, from its side."""
    (xml,) = snapshot.files.values()
    chunks = []
    edges = []
    for w in BeautifulSoup(xml, "lxml-xml").find_all("Weakness"):
        if w["Status"] in RETIRED:
            continue
        native_id = f"CWE-{w['ID']}"
        examples = [
            (ref, text(e.find("Description")))
            for e in w.find_all("Observed_Example")
            if (ref := text(e.find("Reference"))).startswith("CVE-")
        ]
        usage = text(w.find("Usage"))
        sections = [
            f"{w['Name']} (weakness, {str(w['Abstraction']).lower()})",
            text(w.find("Description", recursive=False)),
            text(w.find("Extended_Description", recursive=False)),
            listed(
                "Also known as",
                [alternate(t) for t in w.find_all("Alternate_Term")],
            ),
            f"Likelihood of exploit: {likelihood}"
            if (likelihood := text(w.find("Likelihood_Of_Exploit")))
            else "",
            listed("Consequences", [consequence(c) for c in w.find_all("Consequence")]),
            listed("Detection methods", [detection(d) for d in w.find_all("Detection_Method")]),
            listed("Mitigations", [mitigation(m) for m in w.find_all("Mitigation")]),
            listed("Observed examples", [f"{ref}: {desc}" for ref, desc in examples]),
            f"Mapping CVEs to it: {usage}. {text(w.find('Rationale'))}" if usage else "",
        ]
        chunks.append(
            Chunk(
                source_id=INFO.id,
                native_id=native_id,
                title=str(w["Name"]),
                url=f"{SITE}/{w['ID']}.html",
                source_version=snapshot.version,
                language="en",
                retrieved_at=snapshot.retrieved_at,
                license=INFO.license,
                attribution=INFO.attribution,
                text="\n\n".join(s for s in sections if s),
                heading_path=["weakness"],
                meta={"kind": "weakness", "abstraction": w["Abstraction"], "status": w["Status"]},
            )
        )
        # One link per relation and target, though CWE lists it once per view.
        related = {
            (re.sub(r"(?<!^)(?=[A-Z])", "_", str(r["Nature"])).lower(), f"CWE-{r['CWE_ID']}")
            for r in w.find_all("Related_Weakness")
        }
        edges += [
            Edge(src_id=native_id, rel=rel, dst_id=dst, origin=INFO.id)
            for rel, dst in sorted(related)
        ]
        edges += [
            Edge(src_id=native_id, rel="observed_example", dst_id=ref, origin=INFO.id)
            for ref in dict.fromkeys(ref for ref, _ in examples)
        ]
    return chunks, edges


def alternate(el: Tag) -> str:
    """'XSS: A common abbreviation for Cross-Site Scripting.', or the bare term."""
    note = text(el.find("Description"))
    return f"{text(el.find('Term'))}: {note}" if note else text(el.find("Term"))


def detection(el: Tag) -> str:
    """'Black Box (effectiveness: Moderate): Use the XSS Cheat Sheet ...'."""
    effectiveness = text(el.find("Effectiveness"))
    rating = f" (effectiveness: {effectiveness})" if effectiveness else ""
    return f"{text(el.find('Method'))}{rating}: {text(el.find('Description'))}"


def mitigation(el: Tag) -> str:
    """'Implementation, Architecture and Design (Libraries or Frameworks): Use a vetted ...'."""
    label = ", ".join(text(p) for p in el.find_all("Phase"))
    if strategy := text(el.find("Strategy")):
        label = f"{label} ({strategy})" if label else strategy
    return f"{label}: {text(el.find('Description'))}" if label else text(el.find("Description"))
