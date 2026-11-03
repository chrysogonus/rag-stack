"""The pack's ID formats: what a question names, normalized to the index's native IDs."""

import pytest

from packs.cybersecurity.ids import detect_ids
from packs.cybersecurity.laws import EU_ACTS, GERMAN_LAWS


@pytest.mark.parametrize(
    ("question", "ids"),
    [
        ("What is AML.T0051 and aml.t0051.001?", ["AML.T0051", "AML.T0051.001"]),
        ("Compare AML.TA0005, AML.M0019 and AML.CS0016", ["AML.TA0005", "AML.M0019", "AML.CS0016"]),
        ("Explain LLM01 and LLM02:2025", ["LLM01:2026"]),
        ("What is ASI 06?", ["ASI06"]),
        (
            "Is CVE-2026-26013 the same as GHSA-2G6R-C272-W58R?",
            ["CVE-2026-26013", "GHSA-2g6r-c272-w58r"],
        ),
        ("What does Article 50(1) require?", ["AI Act Art. 50(1)"]),
        ("What does paragraph 2 of Article 50 say?", ["AI Act Art. 50(2)"]),
        ("Was regelt Art. 50 Abs. 1 KI-VO?", ["AI Act Art. 50(1)"]),
        ("Was steht in Artikel 4a?", ["AI Act Art. 4a"]),
        ("Erwägungsgrund 133 und Recital 27", ["Recital 133", "Recital 27"]),
        ("Annex III point 1(a)", ["Annex III 1(a)"]),
        ("Anhang III Nummer 4 Buchstabe b", ["Annex III 4(b)"]),
        # Lettered points of articles without paragraphs and of annexes are units of their own.
        (
            "What is Art. 66(j) and Artikel 16 Buchstabe h?",
            ["AI Act Art. 66(j)", "AI Act Art. 16(h)"],
        ),
        (
            "Annex XIII e, Annex VII point (d), Anhang IV Buchstabe a",
            ["Annex XIII e", "Annex VII d", "Annex IV a"],
        ),
        (
            "Article 5(1)(a) and Annex III and Annex II",
            ["AI Act Art. 5(1)", "Annex III", "Annex II"],
        ),
        # A bare letter followed by a word is prose: "Annex III a list".
        ("Is Annex III a list of uses, and Annex I a set of laws?", ["Annex III", "Annex I"]),
        # ... and so is "e.g."; a sentence's full stop is not.
        ("Explain Annex XIII e. Then Annex VII point (d).", ["Annex XIII e", "Annex VII d"]),
        ("Annex III e.g. covers biometrics", ["Annex III"]),
        ("Wer ist nach § 2 Abs. 3 KI-MIG zuständig?", ["KI-MIG § 2 Abs. 3"]),
        (
            "im Sinne des Artikels 70 Absatz 2 der KI-VO, nach Maßgabe des Anhangs III",
            ["AI Act Art. 70(2)", "Annex III"],
        ),
        ("What does Section 3 of the KI-MIG cover?", ["KI-MIG § 3"]),
        ("Section 2 of Annex I", ["Annex I"]),
        ("How do attackers poison a RAG corpus?", []),
        # ATT&CK, not the technique inside an ATLAS ID
        (
            "T1059.001, t1566 and TA0002 vs. AML.T0051",
            ["AML.T0051", "T1059.001", "T1566", "TA0002"],
        ),
        (
            "Is M1038 used by G0016 (S0154, C0024, DET0001)?",
            ["M1038", "G0016", "S0154", "C0024", "DET0001"],
        ),
        ("Map cwe-79 and CAPEC 66 to D3-MFA", ["CWE-79", "CAPEC-66", "D3-MFA"]),
        (
            "PR.AA-01, AC-2 (1), SI-4 and SSDF PO.1.1",
            ["PR.AA-01", "AC-2(1)", "SI-4", "SSDF PO.1.1"],
        ),
        ("What does AI RMF GOVERN 1.1 ask?", ["AI RMF GOVERN 1.1"]),
        ("A01:2025, A03 and A05:2021", ["A01:2025", "A03:2025"]),
        ("ASVS 1.2.5 and v5.0.0-2.1.1", ["v5.0.0-1.2.5", "v5.0.0-2.1.1"]),
        (
            "Summarize arXiv:2601.01234v2 and arxiv.org/abs/2512.09876",
            ["arXiv:2601.01234", "arXiv:2512.09876"],
        ),
    ],
)
def test_detect_ids(question, ids):
    assert detect_ids(question) == ids


@pytest.mark.parametrize(
    ("question", "ids"),
    [
        ("Was verlangt Art. 21 Abs. 2 NIS2?", ["NIS2 Art. 21(2)"]),
        (
            "Compare NIS2 Article 21 with Article 15 of the AI Act",
            ["NIS2 Art. 21", "AI Act Art. 15"],
        ),
        ("Art. 50 KI-VO", ["AI Act Art. 50"]),
        # No act named: every indexed act, and the reranker decides.
        ("What does Article 5 say?", ["AI Act Art. 5", "NIS2 Art. 5"]),
        ("Recital 12", ["Recital 12", "NIS2 Recital 12"]),
        ("NIS2 Annex I point 2", ["NIS2 Annex I 2"]),
        ("§ 30 Abs. 1 BSIG und § 2 KI-MIG", ["BSIG § 30 Abs. 1", "KI-MIG § 2"]),
        ("Was regelt § 8?", ["KI-MIG § 8", "BSIG § 8"]),
    ],
)
def test_detect_ids_picks_the_act(monkeypatch, question, ids):
    monkeypatch.setitem(EU_ACTS, "nis2", ("NIS2", r"NIS ?2"))
    monkeypatch.setitem(GERMAN_LAWS, "bsig", ("BSIG", "BSIG"))
    assert detect_ids(question) == ids
