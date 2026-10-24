import json
import logging
from datetime import datetime, timedelta
from typing import Any

from rag_stack.ingestion.fetch import Fetcher, FetchError
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["ai-vulns"]
logger = logging.getLogger(__name__)


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    since = datetime.fromisoformat(retrieved_at) - timedelta(days=30 * config["window_months"])
    osv: dict[str, list[dict]] = {}
    for package in config["packages"]:
        label = package.get("label", package["name"])
        query: dict[str, Any] = {
            "package": {"name": package["name"], "ecosystem": package["ecosystem"]}
        }
        vulns: list[dict] = []
        while True:
            page = json.loads(fetcher.post_json(config["osv_url"], query))
            vulns += page.get("vulns", [])
            if not page.get("next_page_token"):
                break
            query["page_token"] = page["next_page_token"]
        osv[label] = vulns

    groups = group_advisories(osv)
    recent = [g for g in groups if published(g) >= since.date().isoformat()]
    nvd: dict[str, dict] = {}
    for group in recent:
        if cve := cve_id(group):
            try:
                found = json.loads(fetcher.get(config["nvd_url"], params={"cveId": cve}))
            except FetchError as error:
                logger.warning("NVD lookup failed for %s: %s", cve, error)
                continue
            if found.get("vulnerabilities"):
                nvd[cve] = found["vulnerabilities"][0]["cve"]
    keep = {r["id"] for g in recent for r in g}
    osv = {label: [v for v in vulns if v["id"] in keep] for label, vulns in osv.items()}
    files = {
        "osv.json": json.dumps(osv, sort_keys=True).encode(),
        "nvd.json": json.dumps(nvd, sort_keys=True).encode(),
        "kev.json": fetcher.get(config["kev_url"]),
    }
    urls = {
        "osv.json": config["osv_url"],
        "nvd.json": config["nvd_url"],
        "kev.json": config["kev_url"],
    }
    return Snapshot(INFO.id, retrieved_at[:10], retrieved_at, files, urls)


def group_advisories(osv: dict[str, list[dict]]) -> list[list[dict]]:
    """OSV lists one issue under several ids (GHSA, PYSEC, CVE alias): merge records sharing one."""
    groups: list[tuple[set[str], list[dict]]] = []
    for vulns in osv.values():
        for vuln in vulns:
            ids = {vuln["id"], *vuln.get("aliases", [])}
            records = [vuln]
            for group in [g for g in groups if g[0] & ids]:
                groups.remove(group)
                ids |= group[0]
                records += group[1]
            groups.append((ids, records))
    return [records for _, records in groups]


def cve_id(group: list[dict]) -> str | None:
    ids = sorted(
        {i for r in group for i in [r["id"], *r.get("aliases", [])] if i.startswith("CVE-")}
    )
    return ids[0] if ids else None


def published(group: list[dict]) -> str:
    """GHSA dates are when the issue was disclosed; PYSEC records are often re-published later."""
    ghsa = [r["published"] for r in group if r["id"].startswith("GHSA-") and r.get("published")]
    return min(ghsa or [r.get("published", "") for r in group])[:10]


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    osv = json.loads(snapshot.files["osv.json"])
    nvd = json.loads(snapshot.files["nvd.json"])
    kev = {v["cveID"]: v for v in json.loads(snapshot.files["kev.json"])["vulnerabilities"]}
    chunks, edges = [], []
    for group in group_advisories(osv):
        cve = cve_id(group)
        record = next((r for r in group if r["id"].startswith("GHSA-")), group[0])
        ids = sorted({i for r in group for i in [r["id"], *r.get("aliases", [])]})
        native_id = cve or record["id"]
        nvd_record = nvd.get(cve or "", {})
        description = next(
            (d["value"] for d in nvd_record.get("descriptions", []) if d["lang"] == "en"), ""
        )
        cwes = sorted(
            {c for r in group for c in r.get("database_specific", {}).get("cwe_ids", [])}
            | {
                d["value"]
                for w in nvd_record.get("weaknesses", [])
                for d in w["description"]
                if d["value"].startswith("CWE-")
            }
        )
        cvss = nvd_cvss(nvd_record)
        in_kev = native_id in kev
        packages = affected(group)
        summary = record.get("summary") or description.split(". ")[0]
        details = record.get("details") or description
        facts = [
            "Affected: " + "; ".join(packages),
            f"CVSS: {cvss}" if cvss else "",
            f"CWE: {', '.join(cwes)}" if cwes else "",
            f"CISA KEV: {'yes, added ' + kev[native_id]['dateAdded'] if in_kev else 'no'}",
            f"Published: {published(group)}",
            f"Aliases: {', '.join(i for i in ids if i != native_id)}",
        ]
        text_from_osv = bool(record.get("details") or record.get("summary"))
        chunks.append(
            Chunk(
                source_id=INFO.id,
                native_id=native_id,
                title=summary,
                url=f"https://nvd.nist.gov/vuln/detail/{cve}"
                if cve
                else f"https://osv.dev/vulnerability/{record['id']}",
                source_version=snapshot.version,
                language="en",
                retrieved_at=snapshot.retrieved_at,
                license="CC-BY-4.0" if text_from_osv else "LicenseRef-NVD-Public-Domain",
                attribution=(
                    f"{record['id']} from the GitHub Advisory Database / OSV (CC BY 4.0); "
                    "NVD (public domain); CISA KEV (CC0)"
                ),
                text=clean("\n".join(f for f in facts if f) + "\n\n" + summary + "\n\n" + details),
                aliases=[i for i in ids if i != native_id],
                meta={
                    "packages": packages,
                    "cwe": cwes,
                    "cvss": cvss,
                    "kev": in_kev,
                    "published": published(group),
                    "references": [r["url"] for r in record.get("references", [])],
                },
            )
        )
        edges += [
            Edge(src_id=native_id, rel="has_weakness", dst_id=c, origin=INFO.id) for c in cwes
        ]
    return chunks, edges


def affected(group: list[dict]) -> list[str]:
    """'name (ecosystem) >=0.1, fixed in 0.2' per affected package range."""
    lines = set()
    for record in group:
        for item in record.get("affected", []):
            package = item.get("package", {})
            for rng in item.get("ranges", []):
                if rng.get("type") == "GIT":
                    continue
                events = rng.get("events", [])
                introduced = [e["introduced"] for e in events if "introduced" in e]
                fixed = [e["fixed"] for e in events if "fixed" in e]
                span = (
                    f">= {introduced[0]}" if introduced and introduced[0] != "0" else "all versions"
                )
                fix = f", fixed in {fixed[0]}" if fixed else ", no fix listed"
                lines.add(f"{package.get('name')} ({package.get('ecosystem')}) {span}{fix}")
    return sorted(lines)


def nvd_cvss(record: dict) -> str:
    metrics = record.get("metrics", {})
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30"):
        if metrics.get(key):
            data = metrics[key][0]["cvssData"]
            severity = data.get("baseSeverity") or metrics[key][0].get("baseSeverity", "")
            return f"{data['baseScore']} {severity} ({data['vectorString']})"
    return ""
