import json
import re
from typing import Any

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean, overview_chunk
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["attack"]
# Each domain's bundle and the kill chain its techniques name their tactics in.
DOMAINS = {
    "enterprise-attack": ("Enterprise", "mitre-attack"),
    "mobile-attack": ("Mobile", "mitre-mobile-attack"),
    "ics-attack": ("ICS", "mitre-ics-attack"),
}
KINDS = {
    "x-mitre-tactic": "tactic",
    "attack-pattern": "technique",
    "course-of-action": "mitigation",
    "intrusion-set": "group",
    "malware": "software: malware",
    "tool": "software: tool",
    "campaign": "campaign",
    "x-mitre-detection-strategy": "detection strategy",
}
EDGE_TYPES = {"uses", "mitigates", "subtechnique-of", "detects", "attributed-to"}
# "(Citation: Name)" markers point into the reference list; ICS names nest one pair of brackets.
CITATION = re.compile(r"\s*\(Citation:(?:[^()]|\([^()]*\))*\)")


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    # Versioned bundles never change once released: the version in the config pins them.
    version = str(config["version"])
    urls = {
        f"{domain}-{version}.json": f"{config['base_url']}/{domain}/{domain}-{version}.json"
        for domain in DOMAINS
    }
    files = {name: fetcher.get(url) for name, url in urls.items()}
    return Snapshot(INFO.id, version, retrieved_at, files, urls)


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    # An object in several domains (a group active in Enterprise and ICS) is one STIX object.
    objects: dict[str, dict[str, Any]] = {}
    for content in snapshot.files.values():
        for obj in json.loads(content)["objects"]:
            if not (obj.get("revoked") or obj.get("x_mitre_deprecated")):
                objects.setdefault(obj["id"], obj)
    ids = {sid: ref(o)["external_id"] for sid, o in objects.items() if o["type"] in KINDS}
    tactics = {
        (DOMAINS[domain][1], o["x_mitre_shortname"]): o
        for o in objects.values()
        if o["type"] == "x-mitre-tactic"
        for domain in o["x_mitre_domains"]
    }

    chunks = []
    edges = []
    for sid, obj in objects.items():
        if obj["type"] not in KINDS:
            continue
        kind = KINDS[obj["type"]]
        native_id = ids[sid]
        achieves = [tactics[(p["kill_chain_name"], p["phase_name"])] for p in kill_chain(obj)]
        edges += [
            Edge(src_id=native_id, rel="achieves", dst_id=ref(t)["external_id"], origin=INFO.id)
            for t in achieves
        ]
        facts = [
            "Tactics: " + ", ".join(f"{t['name']} ({ref(t)['external_id']})" for t in achieves)
            if achieves
            else "",
            aka(obj),
            f"First seen: {obj['first_seen'][:10]}, last seen: {obj['last_seen'][:10]}"
            if "first_seen" in obj and "last_seen" in obj
            else "",
            "Platforms: " + ", ".join(obj["x_mitre_platforms"])
            if obj.get("x_mitre_platforms")
            else "",
            "Domains: " + ", ".join(DOMAINS[d][0] for d in obj["x_mitre_domains"]),
        ]
        parts = [
            f"{obj['name']} ({kind})",
            text(obj.get("description", "")),
            analytics(obj, objects),
            "\n".join(f for f in facts if f),
        ]
        chunks.append(
            Chunk(
                source_id=INFO.id,
                native_id=native_id,
                title=obj["name"],
                url=ref(obj)["url"],
                source_version=snapshot.version,
                language="en",
                retrieved_at=snapshot.retrieved_at,
                license=INFO.license,
                attribution=INFO.attribution,
                text="\n\n".join(p for p in parts if p),
                heading_path=[kind],
                parent_ids=[native_id.split(".")[0]] if "." in native_id else [],
                meta={
                    "kind": kind,
                    "domains": obj["x_mitre_domains"],
                    "created": obj.get("created"),
                    "modified": obj.get("modified"),
                    # Outbound links (papers, news) are kept as metadata and never fetched.
                    "references": [r["url"] for r in obj["external_references"][1:] if "url" in r],
                },
            )
        )

    for domain, (name, _) in DOMAINS.items():
        if f"{domain}-{snapshot.version}.json" not in snapshot.files:
            continue
        chunks.append(
            overview_chunk(
                [
                    c.model_copy(update={"text": c.text.split("\n\n")[1]})  # the description
                    for c in chunks
                    if c.meta["kind"] == "tactic" and domain in c.meta["domains"]
                ],
                native_id=f"ATT&CK {name} Tactics",
                title=f"MITRE ATT&CK {name} tactics: overview",
                url=f"https://attack.mitre.org/tactics/{domain.split('-')[0]}/",
                intro=f"MITRE ATT&CK {snapshot.version} for {name} defines these tactics, "
                "listed by ID (not in matrix order):",
            )
        )

    # Relationships between live objects; their procedure and mitigation text stays out.
    edges += [
        Edge(
            src_id=ids[o["source_ref"]],
            rel=o["relationship_type"],
            dst_id=ids[o["target_ref"]],
            origin=INFO.id,
        )
        for o in objects.values()
        if o["type"] == "relationship"
        and o["relationship_type"] in EDGE_TYPES
        and o["source_ref"] in ids
        and o["target_ref"] in ids
    ]
    return chunks, edges


def ref(obj: dict[str, Any]) -> dict[str, Any]:
    """The ATT&CK reference (ID and page) comes first in every ATT&CK object."""
    return obj["external_references"][0]


def kill_chain(obj: dict[str, Any]) -> list[dict[str, str]]:
    return obj.get("kill_chain_phases", []) if obj["type"] == "attack-pattern" else []


def text(description: str) -> str:
    return clean(CITATION.sub("", description))


def aka(obj: dict[str, Any]) -> str:
    """Other names of a group, campaign or piece of software (the first alias is its name)."""
    others = [a for a in obj.get("aliases", obj.get("x_mitre_aliases", [])) if a != obj["name"]]
    return f"Also known as: {', '.join(others)}" if others else ""


def analytics(obj: dict[str, Any], objects: dict[str, dict[str, Any]]) -> str:
    """A detection strategy has no description of its own: its analytics are its content."""
    lines = []
    for sid in obj.get("x_mitre_analytic_refs", []):
        if analytic := objects.get(sid):
            platforms = ", ".join(analytic.get("x_mitre_platforms", []))
            description = text(analytic["description"])
            lines.append(f"- {ref(analytic)['external_id']} ({platforms}): {description}")
    return "Analytics:\n" + "\n".join(lines) if lines else ""
