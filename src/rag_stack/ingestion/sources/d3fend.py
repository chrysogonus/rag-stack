import json
from typing import Any

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean, overview_chunk
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["d3fend"]
SITE = "https://d3fend.mitre.org"
FILES = ("d3fend.json", "d3fend-full-mappings.json")
# SPARTA (space systems) mappings stay out: SPARTA isn't indexed and has terms of its own.
FRAMEWORKS = {"ATTACKEnterpriseTechnique", "ATTACKICSTechnique"}
# Properties that aren't a technique's relations to digital artifacts.
NOT_RELATIONS = {"d3f:enables", "d3f:kb-reference"}


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    """The ontology and the ATT&CK mappings inferred from it, of one release."""
    version = str(config["version"])
    urls = {name: f"{config['base_url']}/{version}/{name}" for name in FILES}
    files = {name: fetcher.get(url) for name, url in urls.items()}
    graph = json.loads(files["d3fend.json"])["@graph"]
    found = next(
        (n.get("owl:versionInfo") for n in graph if n.get("@type") == "owl:Ontology"), None
    )
    if found != version:
        raise ValueError(f"{urls['d3fend.json']}: not the D3FEND {version} ontology")
    return Snapshot(INFO.id, version, retrieved_at, files, urls)


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    """One chunk per defensive technique (D3-…). The analytic techniques (D3A-…) catalog the
    algorithms detections use, and the tactics have no IDs: the overview lists them."""
    graph = {n["@id"]: n for n in json.loads(snapshot.files["d3fend.json"])["@graph"]}
    techniques = {
        i: n for i, n in graph.items() if str(n.get("d3f:d3fend-id", "")).startswith("D3-")
    }

    def label(i: str) -> str:
        return graph.get(i, {}).get("rdfs:label", i.removeprefix("d3f:"))

    def tactic(i: str) -> str:
        """The tactic a technique or its nearest ancestor enables."""
        node = graph.get(i, {})
        if enabled := ids(node.get("d3f:enables")):
            return label(enabled[0])
        return next((t for p in ids(node.get("rdfs:subClassOf")) if (t := tactic(p))), "")

    chunks = []
    edges = []
    for i, n in techniques.items():
        native_id = n["d3f:d3fend-id"]
        parents = [p for p in ids(n.get("rdfs:subClassOf")) if p in techniques]
        relations: dict[str, list[str]] = {}
        for key, value in n.items():
            if key.startswith("d3f:") and key not in NOT_RELATIONS:
                relations.setdefault(key, []).extend(ids(value))
        kind = f"defensive technique, {tactic(i)}" if tactic(i) else "defensive technique"
        sections = [
            f"{n['rdfs:label']} ({kind})",
            str(n.get("d3f:definition", "")),
            "Also known as: " + ", ".join(synonyms)
            if (synonyms := values(n.get("d3f:synonym")))
            else "",
            "\n".join(
                [f"Part of: {label(p)} ({techniques[p]['d3f:d3fend-id']})" for p in parents]
                + [
                    f"{key.removeprefix('d3f:').replace('-', ' ').capitalize()}: "
                    + ", ".join(dict.fromkeys(label(t) for t in targets))
                    for key, targets in relations.items()
                    if targets
                ]
            ),
            clean("\n\n".join(values(n.get("d3f:kb-article")))),
        ]
        chunks.append(
            Chunk(
                source_id=INFO.id,
                native_id=native_id,
                title=str(n["rdfs:label"]),
                url=f"{SITE}/technique/{i}/",
                source_version=snapshot.version,
                language="en",
                retrieved_at=snapshot.retrieved_at,
                license=INFO.license,
                attribution=INFO.attribution,
                text="\n\n".join(s for s in sections if s),
                heading_path=["defensive technique"],
                meta={"kind": "defensive technique", "tactic": tactic(i)},
            )
        )
        edges += [
            Edge(
                src_id=native_id,
                rel="child_of",
                dst_id=techniques[p]["d3f:d3fend-id"],
                origin=INFO.id,
            )
            for p in parents
        ]

    # Each row links a technique, through the digital artifact it acts on, to an ATT&CK
    # technique acting on the same kind of artifact. Its sub-techniques inherit the row.
    rows = json.loads(snapshot.files["d3fend-full-mappings.json"])["results"]["bindings"]
    countered = {
        (techniques[i]["d3f:d3fend-id"], row["off_tech_id"]["value"])
        for row in rows
        if row["framework_root_iri"]["value"].rsplit("#", 1)[-1] in FRAMEWORKS
        and (i := "d3f:" + row["def_tech"]["value"].rsplit("#", 1)[-1]) in techniques
    }
    edges += [
        Edge(src_id=src, rel="counters", dst_id=dst, origin=INFO.id)
        for src, dst in sorted(countered)
    ]

    tactics = sorted(
        {t for n in techniques.values() for t in ids(n.get("d3f:enables"))},
        key=lambda t: graph[t].get("d3f:display-order", 0),
    )
    chunks.append(
        overview_chunk(
            [
                c.model_copy(
                    update={
                        "title": f"{c.title} ({c.meta['tactic']})",
                        "text": str(n.get("d3f:definition", "")),
                    }
                )
                for c, n in zip(chunks, techniques.values(), strict=True)
                if "d3f:enables" in n
            ],
            native_id="D3FEND Tactics",
            title="MITRE D3FEND tactics: overview",
            url=f"{SITE}/",
            intro=f"MITRE D3FEND {snapshot.version} groups its defensive techniques under "
            f"{len(tactics)} tactics: {', '.join(label(t) for t in tactics)}. Its top-level "
            "techniques, listed by ID, with their tactic:",
        )
    )
    return chunks, edges


def values(value: Any) -> list[Any]:
    """JSON-LD gives one value bare and several as a list."""
    return [] if value is None else value if isinstance(value, list) else [value]


def ids(value: Any) -> list[str]:
    """The node IDs a property points to, skipping literals."""
    return [v["@id"] for v in values(value) if isinstance(v, dict) and "@id" in v]
