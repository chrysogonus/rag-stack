from typing import Any
from urllib.parse import urljoin

import yaml

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["atlas"]
SITE = "https://atlas.mitre.org"
KINDS = {
    "tactics": ("tactic", "tactics"),
    "techniques": ("technique", "techniques"),
    "mitigations": ("mitigation", "mitigations"),
    "case-studies": ("case study", "studies"),
}
EDGE_TYPES = {"achieves", "specializes", "mitigates", "employs"}


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    pointer = fetcher.get(config["latest_url"])
    url = config["latest_url"]
    # On raw.githubusercontent.com a git symlink is served as its target path.
    if len(pointer) < 200 and pointer.strip().endswith(b".yaml"):
        url = urljoin(url, pointer.decode().strip())
        pointer = fetcher.get(url)
    data = yaml.safe_load(pointer)
    version = str(data["collection"]["version"])
    return Snapshot("atlas", version, retrieved_at, {"ATLAS.yaml": pointer}, {"ATLAS.yaml": url})


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    data = yaml.safe_load(snapshot.files["ATLAS.yaml"])
    steps = case_study_steps(data["relationships"])
    chunks = []
    for key, (kind, path) in KINDS.items():
        for native_id, item in data[key].items():
            text = clean(item.get("description", ""))
            if native_id in steps:
                text += "\n\nProcedure:\n" + "\n".join(steps[native_id])
            parent = native_id.rsplit(".", 1)[0] if native_id.count(".") == 2 else None
            chunks.append(
                Chunk(
                    source_id=INFO.id,
                    native_id=native_id,
                    title=item["name"],
                    url=f"{SITE}/{path}/{native_id}",
                    source_version=snapshot.version,
                    language="en",
                    retrieved_at=snapshot.retrieved_at,
                    license=INFO.license,
                    attribution=INFO.attribution,
                    text=f"{item['name']} ({kind})\n\n{text}",
                    heading_path=[kind],
                    parent_ids=[parent] if parent else [],
                    meta={
                        "kind": kind,
                        "created": item.get("created-date"),
                        "modified": item.get("modified-date"),
                        # Outbound links (papers, news) are kept as metadata and never fetched.
                        "references": [r["url"] for r in item.get("references", []) if "url" in r],
                    },
                )
            )
    edges = [
        Edge(
            src_id=rel["source"], rel=rel["relationship-type"], dst_id=rel["target"], origin="atlas"
        )
        for groups in data["relationships"].values()
        for typ, rels in groups.items()
        if typ in EDGE_TYPES
        for rel in rels
    ]
    return chunks, edges


def case_study_steps(relationships: dict[str, dict[str, list[dict]]]) -> dict[str, list[str]]:
    """A case study's procedure is part of its own text: one line per step."""
    steps: dict[str, list[str]] = {}
    for source, groups in relationships.items():
        for rel in groups.get("employs", []):
            if source.startswith("AML.CS") and rel.get("description"):
                description = clean(rel["description"]).replace("\n", " ")
                steps.setdefault(source, []).append(f"- {rel['target']}: {description}")
    return steps
