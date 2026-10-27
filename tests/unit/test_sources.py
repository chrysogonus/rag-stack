"""Parsers against small excerpts of the real sources (tests/fixtures, see NOTICE.md)."""

import json
from dataclasses import replace
from pathlib import Path

from rag_stack.ingestion.models import Snapshot
from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS, SOURCES
from rag_stack.ingestion.sources import (
    ai_vulns,
    atlas,
    attack,
    eu_law,
    gesetze_im_internet,
    owasp_agentic,
    owasp_llm,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
WHEN = "2026-10-24T00:00:00+00:00"


def snapshot(source_id: str, version: str, folder: str, names: list[str]) -> Snapshot:
    files = {name: (FIXTURES / folder / name).read_bytes() for name in names}
    return Snapshot(source_id, version, WHEN, files, {n: f"https://example.org/{n}" for n in names})


def by_id(chunks):
    return {(c.native_id, c.language): c for c in chunks}


def test_atlas_one_chunk_per_object_with_relationships_as_edges():
    chunks, edges = atlas.parse(snapshot("atlas", "2026.09", "atlas", ["ATLAS.yaml"]))

    found = by_id(chunks)
    assert set(found) == {
        ("AML.TA0005", "en"),
        ("AML.T0051", "en"),
        ("AML.T0051.000", "en"),
        ("AML.M0019", "en"),
        ("AML.CS0016", "en"),
        ("ATLAS Tactics", "en"),
    }
    technique = found[("AML.T0051", "en")]
    assert technique.title == "LLM Prompt Injection"
    assert technique.url == "https://atlas.mitre.org/techniques/AML.T0051"
    assert technique.source_version == "2026.09"
    assert technique.license == "Apache-2.0"
    assert "Copyright 2021-2026 MITRE" in technique.attribution
    assert found[("AML.T0051.000", "en")].parent_ids == ["AML.T0051"]
    assert found[("AML.CS0016", "en")].url == "https://atlas.mitre.org/studies/AML.CS0016"
    # Relationships live in the edge table, not in technique or mitigation text.
    assert ("AML.M0019", "mitigates", "AML.T0051") in {(e.src_id, e.rel, e.dst_id) for e in edges}
    assert ("AML.T0051.000", "specializes", "AML.T0051") in {
        (e.src_id, e.rel, e.dst_id) for e in edges
    }
    assert "AML.M0019" not in technique.text
    assert ("AML.TA0005", "adapted_from", "TA0002") in {(e.src_id, e.rel, e.dst_id) for e in edges}
    # A case study's procedure is its own content and stays in its text.
    assert "Procedure:" in found[("AML.CS0016", "en")].text
    overview = found[("ATLAS Tactics", "en")]
    assert overview.text.splitlines()[1:] == [
        "AML.TA0005 Execution: The adversary is trying to run malicious code embedded in AI "
        "artifacts or software."
    ]
    assert "MITRE ATLAS 2026.09" in overview.text and "not in matrix order" in overview.text
    assert overview.url == "https://atlas.mitre.org/tactics"
    assert "Copyright 2021-2026 MITRE" in overview.attribution


def test_atlas_fetch_follows_the_latest_symlink():
    class Fetcher:
        def __init__(self):
            self.urls = []

        def get(self, url):
            self.urls.append(url)
            if url.endswith("ATLAS-latest.yaml"):
                return b"ATLAS-2026.09.yaml\n"
            return (FIXTURES / "atlas/ATLAS.yaml").read_bytes()

    fetcher = Fetcher()
    snap = atlas.fetch(fetcher, {"latest_url": "https://h/dist/v6/ATLAS-latest.yaml"}, WHEN)  # type: ignore[arg-type]

    assert fetcher.urls[-1] == "https://h/dist/v6/ATLAS-2026.09.yaml"
    assert snap.version == "2026.09"


def test_attack_one_chunk_per_live_object_across_domains():
    names = ["enterprise-attack-20.0.json", "ics-attack-20.0.json"]
    chunks, edges = attack.parse(snapshot("attack", "20.0", "attack", names))

    found = by_id(chunks)
    # T1086 is revoked, T0807 deprecated; APT38 is in both bundles but one object; no Mobile
    # bundle, no Mobile overview.
    assert {i for i, _ in found} == {
        "TA0002",
        "T1059",
        "T1059.001",
        "M1038",
        "G0016",
        "G0082",
        "S0154",
        "S0039",
        "C0024",
        "DET0455",
        "TA0104",
        "T0871",
        "M0938",
        "ATT&CK Enterprise Tactics",
        "ATT&CK ICS Tactics",
    }
    powershell = found[("T1059.001", "en")]
    assert powershell.title == "PowerShell"
    assert powershell.url == "https://attack.mitre.org/techniques/T1059/001"
    assert powershell.parent_ids == ["T1059"]
    assert powershell.license == "LicenseRef-MITRE-ATTACK-Terms"
    assert "The MITRE Corporation" in powershell.attribution
    assert powershell.text.startswith("PowerShell (technique)\n\nAdversaries may abuse PowerShell")
    assert "(Citation:" not in powershell.text
    assert "Tactics: Execution (TA0002)\nPlatforms: Windows, Linux, macOS" in powershell.text
    # Both domains have an "execution" tactic: each technique gets its own domain's.
    assert "Tactics: Execution (TA0104)" in found[("T0871", "en")].text
    assert found[("G0082", "en")].meta["domains"] == ["enterprise-attack", "ics-attack"]
    # The first alias is the group's own name.
    assert "Also known as: IRON RITUAL, " in found[("G0016", "en")].text
    assert "Cozy Bear" in found[("G0016", "en")].text
    assert "First seen: 2019-08-01, last seen: 2021-01-01" in found[("C0024", "en")].text
    assert found[("S0039", "en")].heading_path == ["software: tool"]
    detection = found[("DET0455", "en")].text
    assert "Analytics:\n- AN1252 (Windows): Detects behavioral chains" in detection
    triples = {(e.src_id, e.rel, e.dst_id) for e in edges}
    assert {
        ("T1059.001", "subtechnique-of", "T1059"),
        ("M1038", "mitigates", "T1059.001"),
        ("G0016", "uses", "T1059.001"),
        ("DET0455", "detects", "T1059.001"),
        ("C0024", "attributed-to", "G0016"),
        ("T1059.001", "achieves", "TA0002"),
        ("T0871", "achieves", "TA0104"),
    } <= triples
    # Edges to objects outside the snapshot (M1042) or to revoked ones are dropped.
    assert not {t for t in triples if {"M1042", "T1086", "T0807"} & set(t)}
    assert len(edges) == len(triples)
    overview = found[("ATT&CK ICS Tactics", "en")]
    assert overview.text.splitlines()[0] == (
        "MITRE ATT&CK 20.0 for ICS defines these tactics, listed by ID (not in matrix order):"
    )
    assert overview.text.splitlines()[1].startswith("TA0104 Execution: The adversary is trying")


def test_attack_fetch_gets_each_domain_of_the_pinned_release():
    class Fetcher:
        def __init__(self):
            self.urls = []

        def get(self, url):
            self.urls.append(url)
            return b"{}"

    fetcher = Fetcher()
    config = {"base_url": "https://h/attack-stix-data/master", "version": "20.0"}
    snap = attack.fetch(fetcher, config, WHEN)  # type: ignore[arg-type]

    assert fetcher.urls == [
        "https://h/attack-stix-data/master/enterprise-attack/enterprise-attack-20.0.json",
        "https://h/attack-stix-data/master/mobile-attack/mobile-attack-20.0.json",
        "https://h/attack-stix-data/master/ics-attack/ics-attack-20.0.json",
    ]
    assert snap.version == "20.0"
    assert list(snap.files) == [
        "enterprise-attack-20.0.json",
        "mobile-attack-20.0.json",
        "ics-attack-20.0.json",
    ]


def test_owasp_llm_one_chunk_per_section_and_mappings_as_edges():
    names = ["LLM01_PromptInjection.md", "Appendix_A_Related_Framework_Mappings.md"]
    chunks, edges = owasp_llm.parse(snapshot("owasp-llm-2026", "2026@9253e38", "owasp_llm", names))

    *chunks, overview = chunks
    assert {c.native_id for c in chunks} == {"LLM01:2026"}
    assert [c.heading_path[1] for c in chunks] == ["Description", "Types of Prompt Injection"]
    assert overview.native_id == "OWASP LLM Top 10 2026"
    assert overview.text.startswith("The OWASP Top 10 for LLM Applications 2026 lists")
    assert overview.text.splitlines()[1].startswith(
        "LLM01:2026 Prompt Injection: A **prompt-injection vulnerability** occurs when"
    )
    assert overview.url == "https://example.org"
    assert chunks[0].title == "Prompt Injection"
    assert chunks[0].url.endswith("LLM01_PromptInjection.md#description")
    # "####" sub-headings stay inside their "###" section.
    assert "#### Direct Prompt Injection" in chunks[1].text
    triples = {(e.src_id, e.rel, e.dst_id) for e in edges}
    assert ("LLM01:2026", "maps_to", "ASI01") in triples
    assert ("LLM01:2026", "maps_to", "CWE-1427") in triples
    assert ("LLM01:2026", "maps_to_supporting", "CWE-707") in triples


def test_owasp_agentic_entries_skip_the_toc_and_stop_at_the_appendix():
    text = (FIXTURES / "owasp_agentic/asi_excerpt.txt").read_text()
    snap = Snapshot("owasp-agentic-2026", "2026", WHEN, {}, {"agentic-top10.pdf": "https://x"})

    *chunks, overview = owasp_agentic.parse_text(text, snap)

    assert [(c.native_id, c.heading_path[1]) for c in chunks] == [
        ("ASI01", "Description"),
        ("ASI01", "Common Examples of the Vulnerability"),
        ("ASI01", "Example Attack Scenarios"),
        ("ASI01", "Prevention and Mitigation Guidelines"),
        ("ASI02", "Description"),
    ]
    assert chunks[0].title == "Agent Goal Hijack"
    assert chunks[4].title == "Tool Misuse and Exploitation"
    assert "genai.owasp.org" not in " ".join(c.text for c in chunks)
    assert "mapped to things" not in chunks[-1].text
    # Wrapped PDF lines are rejoined, numbered items keep their own line.
    assert "\n2. Indirect Prompt Injection" in chunks[1].text
    # One overview names the list and every entry, from each entry's description.
    assert (overview.native_id, overview.url) == ("OWASP Agentic Top 10 2026", "https://x")
    assert "OWASP Top 10 for Agentic Applications 2026" in overview.title
    assert [line.split(":")[0] for line in overview.text.splitlines()[1:]] == [
        "ASI01 Agent Goal Hijack",
        "ASI02 Tool Misuse and Exploitation",
    ]
    assert "AI Agents exhibit autonomous ability" in overview.text


def test_eu_ai_act_units_in_both_languages_linked_by_unit_key():
    names = ["consolidated_en.xhtml", "consolidated_de.xhtml", "oj_en.xhtml", "oj_de.xhtml"]
    chunks, edges = eu_law.parse(snapshot("eu-ai-act", "02024R1689-20260727", "eu_ai_act", names))

    found = by_id(chunks)
    assert edges == []
    en, de = found[("AI Act Art. 50(1)", "en")], found[("AI Act Art. 50(1)", "de")]
    assert en.text.startswith("Providers shall ensure that AI systems intended to interact")
    assert de.text.startswith("Die Anbieter stellen sicher")
    assert en.unit_key == de.unit_key == "art_50.1"
    assert en.parent_ids == ["AI Act Art. 50"]
    assert en.title.startswith("Article 50 Transparency obligations")
    assert de.title.startswith("Artikel 50 Transparenzpflichten")
    assert en.url.endswith("#art_50")
    assert en.source_version == "02024R1689-20260727"
    assert en.attribution == "© European Union, https://eur-lex.europa.eu"
    # Amendment markers (▼M1) are not part of the legal text.
    assert "▼" not in " ".join(c.text for c in chunks)
    # Definitions in Article 3 are points, cited as Art. 3(1).
    assert "‘AI system’ means" in found[("AI Act Art. 3(1)", "en")].text
    assert found[("AI Act Art. 3(1)", "de")].unit_key == "art_3.1"
    # Annex points and their lettered sub-points.
    assert found[("Annex III 1", "en")].text.startswith("1. Biometrics")
    assert found[("Annex III 1(a)", "en")].text.startswith("(a) remote biometric identification")
    assert found[("Annex III 1(a)", "en")].parent_ids == ["Annex III", "Annex III 1"]
    # Recitals come from the Official Journal text.
    recital = found[("Recital 133", "de")]
    assert recital.text.startswith("Eine Vielzahl von KI-Systemen")
    assert recital.source_version == "OJ 2024/1689"


def test_ki_mig_one_chunk_per_paragraph():
    snap = snapshot("ki-mig", "20260729215513", "ki_mig", ["ki-mig.xml"])
    snap.urls["ki-mig.xml"] = "https://www.gesetze-im-internet.de/ki-mig/"
    chunks, _ = gesetze_im_internet.parse(snap)

    ids = [c.native_id for c in chunks]
    assert ids[:3] == ["KI-MIG § 1", "KI-MIG § 2 Abs. 1", "KI-MIG § 2 Abs. 2"]
    first = chunks[1]
    assert first.language == "de"
    assert first.text.startswith("(1) Die Bundesnetzagentur ist")
    assert first.parent_ids == ["KI-MIG § 2"]
    assert first.url == "https://www.gesetze-im-internet.de/ki-mig/__2.html"
    assert first.source_version == "Stand 2026-07-29, BGBl. I 2026, Nr. 223"
    assert first.license == "LicenseRef-UrhG-5"
    assert first.heading_path == [
        "Abschnitt 1 Zuständige Stellen",
        "§ 2 Zuständige Marktüberwachungsbehörden",
    ]
    # Numbered lists keep one line per item.
    assert "\n1. Institute nach § 1 Absatz 1b" in chunks[3].text


def test_legal_parsers_take_ids_and_licenses_from_the_registry(monkeypatch):
    """Another act through the same parsers: its short name prefixes every ID; only the AI Act
    keeps bare recital and annex IDs."""
    for source_id in ("nis2", "bsig"):
        monkeypatch.setitem(SOURCES, source_id, replace(SOURCES["eu-ai-act"], id=source_id))
    monkeypatch.setitem(EU_ACTS, "nis2", ("NIS2", "NIS2"))
    monkeypatch.setitem(GERMAN_LAWS, "bsig", ("BSIG", "BSIG"))
    names = ["consolidated_en.xhtml", "oj_en.xhtml"]
    act, _ = eu_law.parse(snapshot("nis2", "02022L2555-20230116", "eu_ai_act", names))
    files = {"bsig.xml": (FIXTURES / "ki_mig/ki-mig.xml").read_bytes()}
    snap = Snapshot("bsig", "20251206", WHEN, files, {"bsig.xml": "https://g/bsig_2025/"})
    law, _ = gesetze_im_internet.parse(snap)

    found = by_id(act)
    assert {
        ("NIS2 Art. 50(1)", "en"),
        ("NIS2 Recital 133", "en"),
        ("NIS2 Annex III 1(a)", "en"),
    } <= set(found)
    assert found[("NIS2 Annex III 1(a)", "en")].parent_ids == ["NIS2 Annex III", "NIS2 Annex III 1"]
    assert found[("NIS2 Recital 133", "en")].source_version == "OJ 2022/2555"
    assert law[1].native_id == "BSIG § 2 Abs. 1"
    assert law[1].parent_ids == ["BSIG § 2"]
    assert law[1].url == "https://g/bsig_2025/__2.html"


def test_ai_vulns_merges_aliases_into_one_advisory_per_cve(tmp_path):
    names = ["osv.json", "nvd.json", "kev.json"]
    snap = snapshot("ai-vulns", "2026-10-24", "ai_vulns", names)
    kev = json.loads(snap.files["kev.json"])
    kev["vulnerabilities"].append({"cveID": "CVE-2026-26013", "dateAdded": "2026-03-01"})
    snap.files["kev.json"] = json.dumps(kev).encode()

    chunks, edges = ai_vulns.parse(snap)

    assert len(chunks) == 1
    advisory = chunks[0]
    assert advisory.native_id == "CVE-2026-26013"
    assert set(advisory.aliases) == {"GHSA-2g6r-c272-w58r", "PYSEC-2026-2562"}
    assert advisory.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-26013"
    assert advisory.license == "CC-BY-4.0"
    assert advisory.meta["cvss"].startswith("3.7 LOW")
    assert advisory.meta["kev"] is True
    assert "CWE-918" in advisory.meta["cwe"]
    assert "langchain-core (PyPI) all versions, fixed in 1.2.11" in advisory.meta["packages"]
    assert "CISA KEV: yes, added 2026-03-01" in advisory.text
    assert ("CVE-2026-26013", "has_weakness", "CWE-918") in {
        (e.src_id, e.rel, e.dst_id) for e in edges
    }
