"""The sky and copy this pack had when they lived in the frontend: order places constellations."""

from rag_stack.pack import PACKS, load_pack


def test_the_sky_keeps_its_constellations_in_their_order():
    ui = load_pack("cybersecurity", str(PACKS)).ui

    assert [(s.id, s.label, s.short) for s in ui.sources] == [
        ("atlas", "MITRE ATLAS", "ATLAS"),
        ("attack", "MITRE ATT&CK", "ATT&CK"),
        ("capec", "MITRE CAPEC", "CAPEC"),
        ("cwe", "MITRE CWE", "CWE"),
        ("vulns", "Vulnerabilities", "CVEs"),
        ("d3fend", "MITRE D3FEND", "D3FEND"),
        ("owasp-llm-2026", "OWASP LLM Top 10", "OWASP LLM"),
        ("owasp-agentic-2026", "OWASP Agentic Top 10", "OWASP Agentic"),
        ("eu-ai-act", "EU AI Act", "AI Act"),
        ("ki-mig", "KI-MIG", "KI-MIG"),
    ]


def test_the_welcome_keeps_its_copy_and_starters():
    ui = load_pack("cybersecurity", str(PACKS)).ui

    assert ui.title == "Knowledge base"
    assert ui.heading == "What do you want to know about cybersecurity?"
    assert ui.placeholder == "Ask about cybersecurity"
    assert ui.intro == (
        "Each constellation is one source. When you ask, the passages behind the answer light up. "
        "Answers come from an AI model and can be wrong, so check anything important."
    )
    assert [(s.question, s.source) for s in ui.starters] == [
        ("Which D3FEND techniques counter T1110.001?", "d3fend"),
        ("What is AML.T0051?", "atlas"),
        ("What does Article 50 of the EU AI Act require?", "eu-ai-act"),
    ]
    assert len(ui.musings) == 18
    assert "Asking Bobby Tables to sit down" in ui.musings
