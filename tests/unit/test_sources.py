"""Parsers against small excerpts of the real sources (tests/fixtures, see NOTICE.md)."""

import io
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from rag_stack.ingestion.models import Snapshot
from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS, SOURCES
from rag_stack.ingestion.sources import (
    atlas,
    attack,
    capec,
    cwe,
    d3fend,
    eu_law,
    gesetze_im_internet,
    owasp_agentic,
    owasp_llm,
    vulns,
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


def test_capec_one_chunk_per_live_attack_pattern_with_its_links_as_edges():
    chunks, edges = capec.parse(snapshot("capec", "3.9", "capec", ["capec_v3.9.xml"]))

    found = by_id(chunks)
    # CAPEC-106 is deprecated.
    assert {i for i, _ in found} == {"CAPEC-11", "CAPEC-66", "CAPEC-170", "CAPEC-248"}
    sqli = found[("CAPEC-66", "en")]
    assert sqli.title == "SQL Injection"
    assert sqli.url == "https://capec.mitre.org/data/definitions/66.html"
    assert sqli.license == "LicenseRef-MITRE-CAPEC-Terms"
    assert "The MITRE Corporation" in sqli.attribution
    assert sqli.text.startswith("SQL Injection (attack pattern, standard)\n\nThis attack exploits")
    assert "Likelihood of attack: High\nTypical severity: High" in sqli.text
    assert "Execution flow:\n- 1. Explore: [Survey application] The attacker first" in sqli.text
    assert "WireShark" not in sqli.text  # a step's techniques stay out
    assert (
        "- Confidentiality, Integrity, Availability: Execute Unauthorized Commands "
        "(Run Arbitrary Code)" in sqli.text
    )
    assert "- Use of parameterized queries or stored procedures" in sqli.text
    assert sqli.meta["abstraction"] == "Standard"
    # XHTML paragraphs are flattened to text.
    misclassification = found[("CAPEC-11", "en")].text
    assert (
        "This type of vulnerability has been found in many widely used servers" in misclassification
    )
    assert "<" not in misclassification
    # <br/> keeps a command and each HTTP header on a line of its own.
    fingerprinting = found[("CAPEC-170", "en")].text
    assert "$ nc iis.server.com 80\nGET / HTTP/3.0" in fingerprinting
    assert "HTTP/1.1 200 OK\nServer: Microsoft-IIS/5.0\n" in fingerprinting
    triples = {(e.src_id, e.rel, e.dst_id) for e in edges}
    assert {
        ("CAPEC-66", "child_of", "CAPEC-248"),
        ("CAPEC-66", "related_weakness", "CWE-89"),
        ("CAPEC-11", "maps_to", "T1036.006"),
    } <= triples
    assert not {t for t in triples if t[0] == "CAPEC-106"}


def test_capec_fetch_gets_the_pinned_catalog_and_checks_its_version():
    xml = (FIXTURES / "capec/capec_v3.9.xml").read_bytes()

    class Fetcher:
        def __init__(self):
            self.urls = []

        def get(self, url):
            self.urls.append(url)
            return xml

    fetcher = Fetcher()
    config = {"base_url": "https://h/data/xml", "version": "3.9"}
    snap = capec.fetch(fetcher, config, WHEN)  # type: ignore[arg-type]

    assert fetcher.urls == ["https://h/data/xml/capec_v3.9.xml"]
    assert snap.version == "3.9" and list(snap.files) == ["capec_v3.9.xml"]
    with pytest.raises(ValueError, match="not the CAPEC 3.10 catalog"):
        capec.fetch(fetcher, {**config, "version": "3.10"}, WHEN)  # type: ignore[arg-type]


def test_cwe_one_chunk_per_live_weakness_with_its_links_as_edges():
    chunks, edges = cwe.parse(snapshot("cwe", "4.20", "cwe", ["cwec_v4.20.xml"]))

    found = by_id(chunks)
    # CWE-1187 is deprecated.
    assert {i for i, _ in found} == {"CWE-74", "CWE-79", "CWE-122", "CWE-1427"}
    xss = found[("CWE-79", "en")]
    assert (
        xss.title
        == "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')"
    )
    assert xss.url == "https://cwe.mitre.org/data/definitions/79.html"
    assert xss.license == "LicenseRef-MITRE-CWE-Terms"
    assert "The MITRE Corporation" in xss.attribution
    assert xss.text.startswith(
        "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting') "
        "(weakness, base)\n\nThe product does not neutralize"
    )
    assert "Also known as:\n- XSS: A common abbreviation for Cross-Site Scripting." in xss.text
    assert "Likelihood of exploit: High" in xss.text
    assert "- Black Box (effectiveness: Moderate): Use the XSS Cheat Sheet" in xss.text
    assert "- Architecture and Design (Libraries or Frameworks): Use a vetted library" in xss.text
    assert "- CVE-2006-3568: Stored XSS in a guestbook application." in xss.text
    assert xss.text.endswith(
        "Mapping CVEs to it: Allowed. This CWE entry is at the Base level of abstraction, which is "
        "a preferred level of abstraction for mapping to the root causes of vulnerabilities."
    )
    assert xss.meta == {"kind": "weakness", "abstraction": "Base", "status": "Stable"}
    # A mitigation without a phase and a term without a description get no empty label.
    heap = found[("CWE-122", "en")].text
    assert "- Pre-design: Use a language or compiler" in heap
    assert "Also known as:\n- Heap Overflow\n- Heap Buffer Overflow\n\n" in heap
    # The XML's line wrapping is gone; code examples stay out.
    prompting = found[("CWE-1427", "en")].text
    assert "it is often possible to cause an LLM to ignore the original guidance" in prompting
    assert "invokeChatbot" not in prompting
    triples = {(e.src_id, e.rel, e.dst_id) for e in edges}
    assert {
        ("CWE-79", "child_of", "CWE-74"),
        ("CWE-79", "peer_of", "CWE-352"),
        ("CWE-79", "can_precede", "CWE-494"),
        ("CWE-1427", "child_of", "CWE-77"),
        ("CWE-1427", "observed_example", "CVE-2024-5565"),
    } <= triples
    # CWE-79 is a child of CWE-74 in two views: one edge.
    assert len(triples) == len(edges)
    assert not {t for t in triples if t[0] == "CWE-1187"}


def test_cwe_fetch_unzips_the_pinned_catalog_and_checks_its_version():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.write(FIXTURES / "cwe/cwec_v4.20.xml", "cwec_v4.20.xml")

    class Fetcher:
        def __init__(self):
            self.urls = []

        def get(self, url):
            self.urls.append(url)
            return buffer.getvalue()

    fetcher = Fetcher()
    config = {"base_url": "https://h/data/xml", "version": "4.20"}
    snap = cwe.fetch(fetcher, config, WHEN)  # type: ignore[arg-type]

    assert fetcher.urls == ["https://h/data/xml/cwec_v4.20.xml.zip"]
    assert snap.version == "4.20" and list(snap.files) == ["cwec_v4.20.xml"]
    assert snap.files["cwec_v4.20.xml"] == (FIXTURES / "cwe/cwec_v4.20.xml").read_bytes()


def test_d3fend_one_chunk_per_defensive_technique_with_attack_mappings_as_edges():
    names = ["d3fend.json", "d3fend-full-mappings.json"]
    chunks, edges = d3fend.parse(snapshot("d3fend", "1.6.0", "d3fend", names))

    *chunks, overview = chunks

    found = by_id(chunks)
    # D3A-ABC is an analytic technique, not a defensive one.
    assert {i for i, _ in found} == {"D3-AA", "D3-MFA", "D3-CH", "D3-NTA", "D3-ARMA"}
    mfa = found[("D3-MFA", "en")]
    assert mfa.url == "https://d3fend.mitre.org/technique/d3f:Multi-factorAuthentication/"
    assert mfa.license == "LicenseRef-MITRE-D3FEND-Terms"
    assert "The MITRE Corporation" in mfa.attribution
    # The tactic comes from the parent technique.
    assert mfa.text.startswith(
        "Multi-factor Authentication (defensive technique, Harden)\n\nRequiring proof of two"
    )
    assert "Part of: Agent Authentication (D3-AA)\nUses: Credential\n\n## How it works" in mfa.text
    assert mfa.meta == {"kind": "defensive technique", "tactic": "Harden"}
    assert "Hardens: Credential" in found[("D3-CH", "en")].text
    assert "Enables" not in found[("D3-NTA", "en")].text
    arma = found[("D3-ARMA", "en")].text
    assert arma.startswith("ARMA Model (defensive technique)\n\n")
    assert "Also known as: Autoregressive moving average model" in arma
    assert overview.native_id == "D3FEND Tactics"
    assert overview.text.splitlines()[:2] == [
        "MITRE D3FEND 1.6.0 groups its defensive techniques under 2 tactics: Harden, Detect. "
        "Its top-level techniques, listed by ID, with their tactic:",
        "D3-AA Agent Authentication (Harden): Agent authentication is the process of verifying "
        "the identities of agents to ensure they are authorized and trustworthy participants "
        "within a system.",
    ]
    assert "D3-MFA" not in overview.text  # not top-level
    # Enterprise and ICS mappings; SPARTA's (PER-0005) stay out.
    assert {(e.src_id, e.rel, e.dst_id) for e in edges} == {
        ("D3-MFA", "child_of", "D3-AA"),
        ("D3-MFA", "counters", "T1110.001"),
        ("D3-MFA", "counters", "T0812"),
        ("D3-CH", "counters", "T1110.001"),
        ("D3-CH", "counters", "T0812"),
    }


def test_d3fend_fetch_gets_both_files_of_the_pinned_release_and_checks_its_version():
    files = {n: (FIXTURES / "d3fend" / n).read_bytes() for n in d3fend.FILES}

    class Fetcher:
        def __init__(self):
            self.urls = []

        def get(self, url):
            self.urls.append(url)
            return files[url.rsplit("/", 1)[1]]

    fetcher = Fetcher()
    config = {"base_url": "https://h/ontologies/d3fend", "version": "1.6.0"}
    snap = d3fend.fetch(fetcher, config, WHEN)  # type: ignore[arg-type]

    assert fetcher.urls == [
        "https://h/ontologies/d3fend/1.6.0/d3fend.json",
        "https://h/ontologies/d3fend/1.6.0/d3fend-full-mappings.json",
    ]
    assert snap.version == "1.6.0" and snap.files == files
    with pytest.raises(ValueError, match="not the D3FEND 1.7.0 ontology"):
        d3fend.fetch(fetcher, {**config, "version": "1.7.0"}, WHEN)  # type: ignore[arg-type]


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


def test_vulns_one_chunk_per_cve_from_ai_packages_github_advisories_and_kev():
    names = ["osv.json", "github.json", "nvd.json", "kev.json", "epss.json"]
    snap = snapshot("vulns", "2026-10-24", "vulns", names)
    kev = json.loads(snap.files["kev.json"])
    kev["vulnerabilities"].append({"cveID": "CVE-2026-26013", "dateAdded": "2026-03-01"})
    snap.files["kev.json"] = json.dumps(kev).encode()
    github = json.loads(snap.files["github.json"])
    agno = github[0]
    # A second advisory for one CVE; GitHub's copy of an AI-package advisory from OSV, and an
    # advisory of another package for that CVE; one for a KEV CVE, without CVSS.
    github.append(
        {
            **agno,
            "ghsa_id": "GHSA-0000-0000-0000",
            "identifiers": [],
            "vulnerabilities": [
                {**agno["vulnerabilities"][0], "package": {"ecosystem": "npm", "name": "agno-js"}}
            ],
        }
    )
    github.append({**agno, "ghsa_id": "GHSA-2g6r-c272-w58r", "cve_id": "CVE-2026-26013"})
    github.append({**agno, "ghsa_id": "GHSA-1111-1111-1111", "cve_id": "CVE-2026-26013"})
    github.append(
        {**agno, "ghsa_id": "GHSA-2222-2222-2222", "cve_id": "CVE-2026-110447", "cwes": []}
        | {"cvss_severities": {}}
    )
    snap.files["github.json"] = json.dumps(github).encode()

    chunks, edges = vulns.parse(snap)

    found = {c.native_id: c for c in chunks}
    assert sorted(found) == [
        "CVE-2026-110447",
        "CVE-2026-114625",
        "CVE-2026-26013",
        "CVE-2026-35002",
        "CVE-2026-48705",
        "GHSA-673q-mjm6-r5xr",
    ]
    ai = found["CVE-2026-26013"]
    assert set(ai.aliases) == {"GHSA-1111-1111-1111", "GHSA-2g6r-c272-w58r", "PYSEC-2026-2562"}
    assert "agno (pip) < 2.3.24, fixed in 2.3.24" in ai.meta["packages"]
    assert "CWE-95" in ai.meta["cwe"]
    assert ai.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-26013"
    assert ai.license == "CC-BY-4.0"
    assert ai.meta["cvss"].startswith("3.7 LOW")
    assert ai.meta["kev"] is True
    assert "CWE-918" in ai.meta["cwe"]
    assert "langchain-core (PyPI) all versions, fixed in 1.2.11" in ai.meta["packages"]
    assert "CISA KEV: yes, added 2026-03-01" in ai.text
    assert "EPSS: 0.43% chance of exploitation in the next 30 days (percentile 0.37)" in ai.text

    advisory = found["CVE-2026-35002"]
    assert advisory.title.startswith("Agno: Arbitrary code execution via `eval()`")
    assert advisory.aliases == ["GHSA-0000-0000-0000", "GHSA-m4w4-3r8h-jw98"]
    assert advisory.meta["packages"] == [
        "agno (pip) < 2.3.24, fixed in 2.3.24",
        "agno-js (npm) < 2.3.24, fixed in 2.3.24",
    ]
    assert "CVSS: 9.8 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)" in advisory.text
    assert "Severity (GitHub): critical\nCWE: CWE-95\nCISA KEV: no\nEPSS: 0.84%" in advisory.text
    assert "EPSS by FIRST" in advisory.attribution
    # The snapshot keeps a long advisory's opening; without a score, no EPSS line.
    monai = found["CVE-2026-48705"]
    assert monai.text.endswith(
        "[Cut short; the full advisory: https://github.com/advisories/GHSA-6hp3-vr39-rqw8]"
    )
    assert len(monai.text) < 2500
    assert "EPSS" not in monai.text
    no_cve = found["GHSA-673q-mjm6-r5xr"]
    assert no_cve.url == "https://github.com/advisories/GHSA-673q-mjm6-r5xr"
    assert no_cve.meta["cvss"].startswith("9.5 (CVSS:4.0/")

    in_kev = found["CVE-2026-110447"]
    assert in_kev.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-110447"
    assert in_kev.meta["cvss"].startswith("9.2 CRITICAL (CVSS:4.0/")  # from NVD
    assert in_kev.meta["cwe"] == ["CWE-78"]
    assert in_kev.meta["kev"] is True
    assert in_kev.meta["kind"] == "advisory"

    listed = found["CVE-2026-114625"]
    assert listed.title == "Arista VeloCloud Orchestrator SQL Injection Vulnerability"
    assert listed.license == "LicenseRef-NVD-Public-Domain"
    assert listed.text.startswith("Product: Arista VeloCloud Orchestrator\nCVSS: ")
    assert "CISA KEV: yes, added 2026-10-23; required action: Apply mitigations" in listed.text
    assert {("CVE-2026-26013", "CWE-918"), ("CVE-2026-114625", "CWE-89")} <= {
        (e.src_id, e.dst_id) for e in edges if e.rel == "has_weakness"
    }


def test_vulns_fetch_pages_through_github_and_nvd_and_scores_the_rest_with_epss():
    config = {
        "window_months": 24,
        "osv_url": "https://osv/query",
        "nvd_url": "https://nvd/cves",
        "kev_url": "https://cisa/kev.json",
        "github_url": "https://gh/advisories",
        "severities": ["critical"],
        "epss_url": "https://first/epss",
        "packages": [],
    }
    agno = json.loads((FIXTURES / "vulns/github.json").read_bytes())[0]
    kev = (FIXTURES / "vulns/kev.json").read_bytes()
    nvd = {"CVE-2026-114625": {"id": "CVE-2026-114625", "configurations": ["bulk"]}}

    class Fake:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict | None]] = []

        def get_pages(self, url, params):
            assert params["published"] == "2024-11-03..2026-10-24"
            return [
                json.dumps([{**agno, "description": "x" * 1000 + "\n" + "y" * 1000}]).encode(),
                json.dumps([{**agno, "withdrawn_at": "x"}]).encode(),
            ]

        def get(self, url, params=None):
            self.calls.append((url, params))
            params = params or {}
            if url == config["kev_url"]:
                return kev
            if url == config["nvd_url"]:
                cves = [] if params["startIndex"] else [{"cve": c} for c in nvd.values()]
                return json.dumps({"totalResults": 1, "vulnerabilities": cves}).encode()
            data = [
                {"cve": c, "epss": "0.5", "percentile": "0.9"} for c in params["cve"].split(",")
            ]
            return json.dumps({"data": data}).encode()

    fake = Fake()
    snap = vulns.fetch(fake, config, WHEN)  # type: ignore[arg-type]

    assert [json.loads(snap.files["github.json"])[0]["ghsa_id"]] == ["GHSA-m4w4-3r8h-jw98"]
    [advisory] = json.loads(snap.files["github.json"])
    assert "references" not in advisory
    # A long description keeps its opening lines, cut where a line ends.
    assert advisory["description"] == "x" * 1000 + (
        "\n\n[Cut short; the full advisory: https://github.com/advisories/GHSA-m4w4-3r8h-jw98]"
    )
    assert json.loads(snap.files["nvd.json"]) == {"CVE-2026-114625": {"id": "CVE-2026-114625"}}
    assert ("https://nvd/cves", {"hasKev": "", "startIndex": 0}) in fake.calls
    epss = json.loads(snap.files["epss.json"])
    assert epss["CVE-2026-35002"] == agno["epss"]
    assert epss["CVE-2026-114625"] == {"percentage": 0.5, "percentile": 0.9}
    assert ("https://first/epss", {"cve": "CVE-2026-110447,CVE-2026-114625"}) in fake.calls
