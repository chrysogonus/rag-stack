import json
import logging
from datetime import datetime, timedelta
from typing import Any

from rag_stack.ingestion.fetch import Fetcher, FetchError
from rag_stack.ingestion.models import Chunk, Edge, Snapshot, clean
from rag_stack.ingestion.registry import SOURCES

INFO = SOURCES["vulns"]
logger = logging.getLogger(__name__)
# The advisory and NVD fields parse() reads; the rest (credits, references, configurations) is
# bulk: 12k advisories a snapshot. Advisory descriptions are cut in the snapshot too.
GITHUB_FIELDS = (
    "ghsa_id",
    "cve_id",
    "html_url",
    "summary",
    "description",
    "identifiers",
    "published_at",
    "severity",
    "vulnerabilities",
    "cvss_severities",
    "cwes",
    "epss",
)
NVD_FIELDS = ("id", "published", "descriptions", "metrics", "weaknesses")
# Room for an advisory's opening in its one chunk, next to its facts.
ADVISORY_CHARS = 1500


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
    keep = {r["id"] for g in recent for r in g}
    osv = {label: [v for v in vulns if v["id"] in keep] for label, vulns in osv.items()}

    window = f"{since.date().isoformat()}..{retrieved_at[:10]}"
    github = [
        {k: a.get(k) for k in GITHUB_FIELDS} | {"description": opening(a)}
        for severity in config["severities"]
        for page in fetcher.get_pages(
            config["github_url"],
            params={"type": "reviewed", "severity": severity, "published": window, "per_page": 100},
        )
        for a in json.loads(page)
        if not a.get("withdrawn_at")
    ]
    kev = fetcher.get(config["kev_url"])

    # NVD's records of every CVE in KEV, a page of up to 2,000 at a time, then the AI-package
    # CVEs not among them one by one.
    nvd: dict[str, dict] = {}
    start = 0
    while True:
        page = json.loads(
            fetcher.get(config["nvd_url"], params={"hasKev": "", "startIndex": start})
        )
        nvd |= {v["cve"]["id"]: trimmed(v["cve"]) for v in page["vulnerabilities"]}
        start += len(page["vulnerabilities"])
        if not page["vulnerabilities"] or start >= page["totalResults"]:
            break
    for cve in sorted({c for g in recent if (c := cve_id(g))} - nvd.keys()):
        try:
            found = json.loads(fetcher.get(config["nvd_url"], params={"cveId": cve}))
        except FetchError as error:
            logger.warning("NVD lookup failed for %s: %s", cve, error)
            continue
        if found.get("vulnerabilities"):
            nvd[cve] = trimmed(found["vulnerabilities"][0]["cve"])

    # GitHub's advisories carry FIRST's EPSS score; FIRST's API gives the rest, 100 per request.
    epss = {a["cve_id"]: a["epss"] for a in github if a["cve_id"] and a["epss"]}
    cves = {v["cveID"] for v in json.loads(kev)["vulnerabilities"]}
    cves |= {c for g in recent if (c := cve_id(g))} | {a["cve_id"] for a in github if a["cve_id"]}
    missing = sorted(cves - epss.keys())
    for i in range(0, len(missing), 100):
        found = json.loads(
            fetcher.get(config["epss_url"], params={"cve": ",".join(missing[i : i + 100])})
        )
        epss |= {
            d["cve"]: {"percentage": float(d["epss"]), "percentile": float(d["percentile"])}
            for d in found["data"]
        }

    files = {
        "osv.json": json.dumps(osv, sort_keys=True).encode(),
        "github.json": json.dumps(github, sort_keys=True).encode(),
        "nvd.json": json.dumps(nvd, sort_keys=True).encode(),
        "kev.json": kev,
        "epss.json": json.dumps(epss, sort_keys=True).encode(),
    }
    urls = {
        "osv.json": config["osv_url"],
        "github.json": config["github_url"],
        "nvd.json": config["nvd_url"],
        "kev.json": config["kev_url"],
        "epss.json": config["epss_url"],
    }
    return Snapshot(INFO.id, retrieved_at[:10], retrieved_at, files, urls)


def opening(advisory: dict) -> str:
    """An advisory's description up to ADVISORY_CHARS: the rest is often a proof of concept."""
    description = advisory.get("description") or ""
    if len(description) <= ADVISORY_CHARS:
        return description
    cut = description[:ADVISORY_CHARS].rsplit("\n", 1)[0]
    return f"{cut}\n\n[Cut short; the full advisory: {advisory['html_url']}]"


def trimmed(record: dict) -> dict:
    return {k: record[k] for k in NVD_FIELDS if k in record}


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
    """One chunk per CVE (an advisory without one keeps its GHSA id): the AI packages' advisories
    from OSV, then GitHub's critical and high ones, then the rest of KEV from NVD."""
    files = {name: json.loads(data) for name, data in snapshot.files.items()}
    nvd, epss = files["nvd.json"], files["epss.json"]
    kev = {v["cveID"]: v for v in files["kev.json"]["vulnerabilities"]}
    entries = [from_osv(group, nvd) for group in group_advisories(files["osv.json"])]
    seen = {i: e for e in entries for i in [e["id"], *e["aliases"]]}
    # Now and then GitHub files one CVE under two advisories: they share its chunk.
    advisories: dict[str, list[dict]] = {}
    for a in files["github.json"]:
        if a["ghsa_id"] in seen:
            continue  # OSV's copy of the same advisory
        if e := seen.get(a["cve_id"] or ""):
            # Another package's advisory for an AI-package CVE.
            e["packages"] = sorted({*e["packages"], *(package(v) for v in a["vulnerabilities"])})
            e["aliases"] = sorted({*e["aliases"], a["ghsa_id"]})
            e["cwes"] |= {c["cwe_id"] for c in a["cwes"]}
        else:
            advisories.setdefault(a["cve_id"] or a["ghsa_id"], []).append(a)
    entries += [from_github(group, nvd.get(cve, {})) for cve, group in advisories.items()]
    seen |= dict.fromkeys(advisories)
    entries += [from_kev(v, nvd.get(cve, {})) for cve, v in kev.items() if cve not in seen]

    chunks, edges = [], []
    for e in entries:
        listed, score = kev.get(e["id"]), epss.get(e["id"])
        cwes = sorted({*e["cwes"], *(listed or {}).get("cwes", [])})
        facts = [
            "Affected: " + "; ".join(e["packages"]) if e["packages"] else "",
            *e["facts"],
            f"CWE: {', '.join(cwes)}" if cwes else "",
            "CISA KEV: " + (kev_facts(listed) if listed else "no"),
            f"EPSS: {score['percentage']:.2%} chance of exploitation in the next 30 days "
            f"(percentile {score['percentile']:.2f})"
            if score
            else "",
            f"Published: {e['published']}",
            f"Aliases: {', '.join(e['aliases'])}" if e["aliases"] else "",
        ]
        chunks.append(
            Chunk(
                source_id=INFO.id,
                native_id=e["id"],
                title=e["title"],
                url=f"https://nvd.nist.gov/vuln/detail/{e['id']}"
                if e["id"].startswith("CVE-")
                else e["url"],
                source_version=snapshot.version,
                language="en",
                retrieved_at=snapshot.retrieved_at,
                license=e["license"],
                attribution=e["credit"] + ("; EPSS by FIRST (first.org/epss)" if score else ""),
                text=clean("\n".join(f for f in facts if f) + "\n\n" + e["body"]),
                aliases=e["aliases"],
                meta={
                    **e["meta"],
                    "packages": e["packages"],
                    "cwe": cwes,
                    "kev": bool(listed),
                    "epss": score["percentage"] if score else None,
                    "published": e["published"],
                },
            )
        )
        edges += [Edge(src_id=e["id"], rel="has_weakness", dst_id=c, origin=INFO.id) for c in cwes]
    return chunks, edges


def from_osv(group: list[dict], nvd: dict[str, dict]) -> dict[str, Any]:
    """An AI package's advisory, with its full text: AI security is the specialty."""
    cve = cve_id(group)
    record = next((r for r in group if r["id"].startswith("GHSA-")), group[0])
    native_id = cve or record["id"]
    nvd_record = nvd.get(cve or "", {})
    description = nvd_description(nvd_record)
    cvss = nvd_cvss(nvd_record)
    packages = affected(group)
    summary = record.get("summary") or description.split(". ")[0]
    return {
        "id": native_id,
        "aliases": sorted(
            {i for r in group for i in [r["id"], *r.get("aliases", [])]} - {native_id}
        ),
        "title": summary,
        "url": f"https://osv.dev/vulnerability/{record['id']}",
        "packages": packages,
        "facts": [f"CVSS: {cvss}" if cvss else ""],
        "cwes": {c for r in group for c in r.get("database_specific", {}).get("cwe_ids", [])}
        | nvd_cwes(nvd_record),
        "published": published(group),
        "body": summary + "\n\n" + (record.get("details") or description),
        "license": "CC-BY-4.0"
        if record.get("details") or record.get("summary")
        else "LicenseRef-NVD-Public-Domain",
        "credit": f"{record['id']} from the GitHub Advisory Database / OSV (CC BY 4.0); "
        "NVD (public domain); CISA KEV (CC0)",
        "meta": {
            "kind": "AI package advisory",
            "cvss": cvss,
            "references": [r["url"] for r in record.get("references", [])],
        },
    }


def from_github(group: list[dict], record: dict) -> dict[str, Any]:
    """A GitHub-reviewed advisory: its description as fetch() cut it. NVD's record (fetched for
    KEV CVEs) fills in a missing CVSS and adds its CWEs."""
    first = group[0]
    native_id = first["cve_id"] or first["ghsa_id"]
    packages = sorted({package(v) for a in group for v in a["vulnerabilities"]})
    cvss = github_cvss(first) or nvd_cvss(record)
    return {
        "id": native_id,
        "aliases": sorted(
            {i for a in group for i in [a["ghsa_id"], *(x["value"] for x in a["identifiers"])]}
            - {native_id}
        ),
        "title": first["summary"],
        "url": first["html_url"],
        "packages": packages,
        "facts": [f"CVSS: {cvss}" if cvss else "", f"Severity (GitHub): {first['severity']}"],
        "cwes": {c["cwe_id"] for a in group for c in a["cwes"]} | nvd_cwes(record),
        "published": first["published_at"][:10],
        "body": first["summary"] + "\n\n" + first["description"],
        "license": "CC-BY-4.0",
        "credit": f"{first['ghsa_id']} from the GitHub Advisory Database (CC BY 4.0); "
        "CISA KEV (CC0)",
        "meta": {"kind": "advisory", "cvss": cvss},
    }


def from_kev(listed: dict, record: dict) -> dict[str, Any]:
    """A KEV entry without an advisory here: CISA's summary and NVD's description."""
    cvss = nvd_cvss(record)
    description = nvd_description(record)
    product = f"{listed['vendorProject']} {listed['product']}"
    return {
        "id": listed["cveID"],
        "aliases": [],
        "packages": [],
        "title": listed["vulnerabilityName"],
        "url": "",
        "facts": [f"Product: {product}", f"CVSS: {cvss}" if cvss else ""],
        "cwes": nvd_cwes(record),
        "published": record.get("published", listed["dateAdded"])[:10],
        "body": "\n\n".join(
            dict.fromkeys(t for t in [listed["shortDescription"], description] if t)
        ),
        "license": "LicenseRef-NVD-Public-Domain",
        "credit": "CISA KEV (CC0); NVD (public domain)",
        "meta": {"kind": "known exploited vulnerability", "product": product, "cvss": cvss},
    }


def kev_facts(listed: dict) -> str:
    """'yes, added 2026-03-01, used in ransomware campaigns; required action: ...'."""
    ransomware = (
        ", used in ransomware campaigns"
        if listed.get("knownRansomwareCampaignUse") == "Known"
        else ""
    )
    action = f"; required action: {a}" if (a := listed.get("requiredAction")) else ""
    return f"yes, added {listed['dateAdded']}{ransomware}{action}"


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


def package(vulnerability: dict) -> str:
    """'agno (pip) < 2.3.24, fixed in 2.3.24', from a GitHub advisory."""
    name = f"{vulnerability['package']['name']} ({vulnerability['package']['ecosystem']})"
    fixed = vulnerability.get("first_patched_version")
    fix = f", fixed in {fixed}" if fixed else ", no fix listed"
    return f"{name} {vulnerability.get('vulnerable_version_range') or 'all versions'}{fix}"


def github_cvss(advisory: dict) -> str:
    for key in ("cvss_v4", "cvss_v3"):
        found = (advisory.get("cvss_severities") or {}).get(key) or {}
        if found.get("vector_string"):
            return f"{found['score']} ({found['vector_string']})"
    return ""


def nvd_description(record: dict) -> str:
    return next((d["value"] for d in record.get("descriptions", []) if d["lang"] == "en"), "")


def nvd_cwes(record: dict) -> set[str]:
    return {
        d["value"]
        for w in record.get("weaknesses", [])
        for d in w["description"]
        if d["value"].startswith("CWE-")
    }


def nvd_cvss(record: dict) -> str:
    metrics = record.get("metrics", {})
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30"):
        if metrics.get(key):
            data = metrics[key][0]["cvssData"]
            severity = data.get("baseSeverity") or metrics[key][0].get("baseSeverity", "")
            return f"{data['baseScore']} {severity} ({data['vectorString']})"
    return ""
