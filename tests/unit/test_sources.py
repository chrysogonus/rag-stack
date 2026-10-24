"""Parsers against small excerpts of the real sources (tests/fixtures, see NOTICE.md)."""

import json
from pathlib import Path

from rag_stack.ingestion.models import Snapshot
from rag_stack.ingestion.sources import (
    ai_vulns,
    atlas,
    eu_ai_act,
    ki_mig,
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
    # A case study's procedure is its own content and stays in its text.
    assert "Procedure:" in found[("AML.CS0016", "en")].text


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


def test_owasp_llm_one_chunk_per_section_and_mappings_as_edges():
    names = ["LLM01_PromptInjection.md", "Appendix_A_Related_Framework_Mappings.md"]
    chunks, edges = owasp_llm.parse(snapshot("owasp-llm-2026", "2026@9253e38", "owasp_llm", names))

    assert {c.native_id for c in chunks} == {"LLM01:2026"}
    assert [c.heading_path[1] for c in chunks] == ["Description", "Types of Prompt Injection"]
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

    chunks = owasp_agentic.parse_text(text, snap)

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


def test_eu_ai_act_units_in_both_languages_linked_by_unit_key():
    names = ["consolidated_en.xhtml", "consolidated_de.xhtml", "oj_en.xhtml", "oj_de.xhtml"]
    chunks, edges = eu_ai_act.parse(
        snapshot("eu-ai-act", "02024R1689-20260727", "eu_ai_act", names)
    )

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
    chunks, _ = ki_mig.parse(snapshot("ki-mig", "20260729215513", "ki_mig", ["ki-mig.xml"]))

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
