from pathlib import Path

import pytest
from fakes.embeddings import FakeEmbedder, FakeReranker, FakeSparseEmbedder, chunk
from qdrant_client import QdrantClient

from rag_stack.config import Settings
from rag_stack.db.edges import EdgeGraph
from rag_stack.ingestion.models import Edge, Snapshot
from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS, SOURCES
from rag_stack.ingestion.sources import atlas, eu_law
from rag_stack.retrieval import retriever
from rag_stack.retrieval.fusion import rrf
from rag_stack.retrieval.ids import detect_ids
from rag_stack.retrieval.index import catalog_label, ensure_collection, index_source
from rag_stack.retrieval.language import detect_language
from rag_stack.retrieval.retriever import KnowledgeBase

pytestmark = pytest.mark.anyio
FIXTURES = Path(__file__).parents[1] / "fixtures"


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


def test_rrf_rewards_items_ranked_high_in_several_lists():
    # c: 1/63 + 1/61 = 0.03227 > b: 2/62 = 0.03226 > a: 1/61 > d: 1/63
    assert rrf([["a", "b", "c"], ["c", "b", "d"]]) == ["c", "b", "a", "d"]
    # With a small k, rank 1 in one list beats rank 2 in another.
    assert rrf([["a", "b"], ["c"]], k=1) == ["a", "c", "b"]


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Welche Pflichten haben Anbieter nach Artikel 50?", "de"),
        ("Was regelt das KI-MIG?", "de"),
        ("What does Article 50 require from providers?", "en"),
        ("List the mitigations for AML.T0051", "en"),
    ],
)
def test_detect_language(text, language):
    assert detect_language(text) == language


def test_edge_graph_neighbors_in_both_directions_and_by_relation():
    graph = EdgeGraph(
        [
            Edge(src_id="AML.M0019", rel="mitigates", dst_id="AML.T0051", origin="atlas"),
            Edge(src_id="AML.T0051", rel="achieves", dst_id="AML.TA0005", origin="atlas"),
            Edge(src_id="LLM01:2026", rel="maps_to", dst_id="AML.TA0005", origin="owasp"),
        ]
    )

    assert graph.neighbors("AML.T0051") == ["AML.M0019", "AML.TA0005"]
    assert graph.neighbors("AML.T0051", {"mitigates"}) == ["AML.M0019"]
    assert graph.neighbors("AML.TA0005") == ["AML.T0051", "LLM01:2026"]
    assert graph.neighbors("unknown") == []


@pytest.fixture
def kb() -> KnowledgeBase:
    def load(module, source_id, version, folder, names):
        files = {n: (FIXTURES / folder / n).read_bytes() for n in names}
        snap = Snapshot(
            source_id, version, "2026-10-24", files, {n: f"https://x/{n}" for n in files}
        )
        return module.parse(snap)

    atlas_chunks, atlas_edges = load(atlas, "atlas", "2026.09", "atlas", ["ATLAS.yaml"])
    act_chunks, _ = load(
        eu_law,
        "eu-ai-act",
        "02024R1689-20260727",
        "eu_ai_act",
        ["consolidated_en.xhtml", "consolidated_de.xhtml", "oj_en.xhtml", "oj_de.xhtml"],
    )
    client = QdrantClient(":memory:")
    embedder, sparse = FakeEmbedder(), FakeSparseEmbedder()
    ensure_collection(client, "kb", embedder.dim)
    index_source(client, "kb", "atlas", "sha-a", atlas_chunks, embedder, sparse)
    index_source(client, "kb", "eu-ai-act", "sha-b", act_chunks, embedder, sparse)
    return KnowledgeBase(
        client, "kb", embedder, sparse, FakeReranker(), EdgeGraph(atlas_edges), min_score=2.0
    )


async def test_exact_ids_come_first(kb):
    found = await kb.retrieve("Tell me about AML.T0051 and prompt injection")

    assert found[0].chunk.native_id == "AML.T0051"
    assert found[0].via == "id"


async def test_a_whole_article_returns_its_paragraphs(kb):
    found = await kb.retrieve("What does Article 50 say?")

    ids = [r.chunk.native_id for r in found if r.via == "id"]
    assert set(ids) == {f"AI Act Art. 50({p})" for p in range(1, 5)}


async def test_legal_text_comes_in_the_language_of_the_question(kb):
    german = await kb.retrieve("Was regelt Art. 50 Abs. 1?")
    english = await kb.retrieve("What does Article 50(1) say?")

    assert (german[0].chunk.native_id, german[0].chunk.language) == ("AI Act Art. 50(1)", "de")
    assert (english[0].chunk.native_id, english[0].chunk.language) == ("AI Act Art. 50(1)", "en")
    # Only one language version of each unit.
    assert len({r.chunk.unit_key for r in german}) == len(german)


async def test_questions_about_mitigations_add_graph_neighbors(kb):
    found = await kb.retrieve("Which mitigations address AML.T0051?")

    graph = [r.chunk for r in found if r.via == "graph"]
    assert [c.native_id for c in graph] == ["AML.M0019"]
    # The edge isn't in either text, so the chunk carries it for the prompt.
    assert graph[0].meta["relation"] == "AML.M0019 mitigates AML.T0051"


async def test_follow_up_without_ids_uses_the_previous_question(kb):
    found = await kb.retrieve("Which mitigations address it?", context="What is AML.T0051?")

    assert found[0].chunk.native_id == "AML.T0051"
    assert [r.chunk.native_id for r in found if r.via == "graph"] == ["AML.M0019"]


@pytest.mark.parametrize("question", ["How do I defend against it?", "Wie schütze ich mich davor?"])
async def test_a_follow_up_asking_how_to_defend_adds_the_mitigations(kb, question):
    found = await kb.retrieve(question, context="What is AML.T0051?")

    assert found[0].chunk.native_id == "AML.T0051"
    assert [r.chunk.native_id for r in found if r.via == "graph"] == ["AML.M0019"]


async def test_a_follow_up_searches_and_reranks_with_the_previous_question(kb):
    await kb.retrieve("How do I defend against it?", context="What is AML.T0051?")

    assert kb.reranker.calls[-1][0] == "What is AML.T0051? How do I defend against it?"


async def test_hybrid_hits_below_the_reranker_floor_are_dropped(kb):
    assert await kb.retrieve("capital city of France") == []


async def test_hybrid_search_finds_units_by_content(kb):
    found = await kb.retrieve("remote biometric identification systems")

    assert found[0].chunk.native_id == "Annex III 1(a)"
    assert found[0].via == "hybrid"


async def test_a_list_question_finds_the_list_overview(kb):
    found = await kb.retrieve("Which tactics does MITRE ATLAS define?")

    assert found[0].chunk.native_id == "ATLAS Tactics"
    assert "AML.TA0005 Execution" in found[0].chunk.text


async def test_catalog_names_each_source_once_without_versions(kb):
    # The fixture index holds two EU AI Act versions (consolidated and OJ).
    assert await kb.catalog() == ["EU AI Act (Regulation (EU) 2024/1689)", "MITRE ATLAS"]


async def test_a_retired_source_still_served_is_named_by_its_id(kb, monkeypatch):
    monkeypatch.delitem(SOURCES, "atlas")

    assert await kb.catalog() == ["EU AI Act (Regulation (EU) 2024/1689)", "atlas"]
    assert catalog_label(chunk("AML.T0051")) == "atlas 2026.09"


def test_index_source_skips_an_unchanged_snapshot_and_replaces_a_changed_one():
    client = QdrantClient(":memory:")
    embedder, sparse = FakeEmbedder(), FakeSparseEmbedder()
    ensure_collection(client, "kb", embedder.dim)
    first = [chunk("AML.T0001"), chunk("AML.T0002")]

    assert index_source(client, "kb", "atlas", "v1", first, embedder, sparse).endswith("2 chunks")
    assert "unchanged" in index_source(client, "kb", "atlas", "v1", first, embedder, sparse)
    index_source(client, "kb", "atlas", "v2", [chunk("AML.T0003")], embedder, sparse)

    points, _ = client.scroll("kb", limit=10)
    assert [p.payload["native_id"] for p in points if p.payload] == ["AML.T0003"]


def test_lookups_by_id_return_every_match_not_just_the_first_page():
    client = QdrantClient(":memory:")
    embedder, sparse = FakeEmbedder(), FakeSparseEmbedder()
    ensure_collection(client, "kb", embedder.dim)
    # 300 parts of one article: more than one page of a Qdrant scroll.
    parts = [
        chunk(f"AI Act Art. 3({n})", source_id="eu-ai-act", parent_ids=["AI Act Art. 3"])
        for n in range(1, 301)
    ]
    index_source(client, "kb", "eu-ai-act", "v1", parts, embedder, sparse)
    kb = KnowledgeBase(client, "kb", embedder, sparse, FakeReranker(), EdgeGraph([]))

    assert len(kb.by_ids(["AI Act Art. 3"])) == 300


async def test_without_named_ids_search_hits_come_before_graph_neighbors(kb):
    found = await kb.retrieve("which mitigation controls access to production models and data")

    assert found[0].via == "hybrid"
    vias = [r.via for r in found]
    assert vias == sorted(vias, key=lambda v: v != "hybrid")


async def test_without_named_ids_an_edge_between_lower_search_hits_reaches_the_prompt():
    # The best search hit is unrelated; the two linked units come second and third.
    question = "can file integrity monitoring counter spearphishing link attacks"
    detection = chunk("DET0878", question + " detection", source_id="attack")
    countermeasure = chunk("D3-FIM", "file integrity monitoring", source_id="d3fend")
    technique = chunk("T1566.002", "spearphishing link", source_id="attack")
    edge = Edge(src_id="D3-FIM", rel="counters", dst_id="T1566.002", origin="d3fend")
    kb = small_kb([detection, countermeasure, technique], [edge])

    found = await kb.retrieve(question)

    assert found[0].chunk.native_id == "DET0878"
    relations = {r.chunk.native_id: r.chunk.meta.get("relation") for r in found}
    assert "D3-FIM counters T1566.002" in relations.values()


@pytest.mark.parametrize(
    ("question", "kept"),
    [
        ("Which risks map to LLM01:2026?", 3),
        # Asking for another source's units is asking for that list: the named unit gets one
        # section ahead of it (its others may follow as search hits).
        ("Which ASI risks map to LLM01:2026?", 1),
        # Its own source isn't another one.
        ("Which LLM Top 10 entries map to LLM01:2026?", 3),
    ],
)
async def test_a_named_unit_keeps_only_its_best_sections_so_related_units_fit(question, kept):
    sections = [
        chunk(
            "LLM01:2026",
            f"prompt injection section {i}",
            source_id="owasp-llm-2026",
            heading_path=[str(i)],
        )
        for i in range(6)
    ]
    for i, section in enumerate(sections):
        section.chunk_index = i
    asi = chunk("ASI01", "agent goal hijack", source_id="owasp-agentic-2026")
    client = QdrantClient(":memory:")
    embedder, sparse = FakeEmbedder(), FakeSparseEmbedder()
    ensure_collection(client, "kb", embedder.dim)
    index_source(client, "kb", "owasp-llm-2026", "s", sections, embedder, sparse)
    index_source(client, "kb", "owasp-agentic-2026", "s", [asi], embedder, sparse)
    graph = EdgeGraph([Edge(src_id="LLM01:2026", rel="maps_to", dst_id="ASI01", origin="owasp")])
    kb = KnowledgeBase(client, "kb", embedder, sparse, FakeReranker(), graph, limit=4)

    found = await kb.retrieve(question)

    assert [r.chunk.native_id for r in found][: kept + 1] == ["LLM01:2026"] * kept + ["ASI01"]


def small_kb(chunks, edges, **options) -> KnowledgeBase:
    client = QdrantClient(":memory:")
    embedder, sparse = FakeEmbedder(), FakeSparseEmbedder()
    ensure_collection(client, "kb", embedder.dim)
    for source_id in {c.source_id for c in chunks}:
        own = [c for c in chunks if c.source_id == source_id]
        index_source(client, "kb", source_id, "s", own, embedder, sparse)
    return KnowledgeBase(
        client, "kb", embedder, sparse, FakeReranker(), EdgeGraph(edges), **options
    )


async def test_a_search_hit_that_is_also_a_graph_neighbor_keeps_its_relation():
    technique = chunk("AML.T0001", "prompt injection mitigation")
    mitigation = chunk("AML.M0001", "prompt injection mitigation control")
    edge = Edge(src_id="AML.M0001", rel="mitigates", dst_id="AML.T0001", origin="atlas")
    kb = small_kb([technique, mitigation], [edge], min_score=1.0)

    found = await kb.retrieve("prompt injection mitigation")

    relations = {r.chunk.native_id: r.chunk.meta.get("relation") for r in found}
    assert set(relations) == {"AML.T0001", "AML.M0001"}
    assert "AML.M0001 mitigates AML.T0001" in relations.values()


@pytest.mark.parametrize(
    "question",
    ["Does D3-SCF counter T1505.002?", "How does D3-SCF defend against T1505.002?"],
)
async def test_an_edge_between_two_named_units_reaches_the_prompt(question):
    # The link is only in the edge data: without it on a named unit, the model denies it.
    countermeasure = chunk("D3-SCF", "system call filtering", source_id="d3fend")
    technique = chunk("T1505.002", "transport agent", source_id="attack")
    edge = Edge(src_id="D3-SCF", rel="counters", dst_id="T1505.002", origin="d3fend")
    kb = small_kb([countermeasure, technique], [edge])

    found = await kb.retrieve(question)

    assert [(r.chunk.native_id, r.via) for r in found] == [("D3-SCF", "id"), ("T1505.002", "id")]
    assert {r.chunk.meta.get("relation") for r in found} == {"D3-SCF counters T1505.002"}


async def test_the_reranker_picks_which_neighbors_are_kept():
    # 20 groups use the technique; edge order lists the off-topic ones first.
    technique = chunk("T1059", "command and scripting interpreter", source_id="attack")
    groups = [
        chunk(f"G{i:04d}", "powershell" if i > 12 else "unrelated", source_id="attack")
        for i in range(1, 21)
    ]
    edges = [Edge(src_id=g.native_id, rel="uses", dst_id="T1059", origin="attack") for g in groups]
    kb = small_kb([technique, *groups], edges, limit=20)

    found = await kb.retrieve("Which groups are related to T1059 with powershell?")

    kept = [r.chunk.native_id for r in found if r.via == "graph"]
    assert len(kept) == retriever.MAX_NEIGHBORS
    assert set(kept[:8]) == {f"G{i:04d}" for i in range(13, 21)}


async def test_a_relation_with_few_edges_is_not_crowded_out_by_one_with_many():
    # CWE-89 has hundreds of CVEs and a handful of CAPEC patterns; the CVE edges come first.
    weakness = chunk("CWE-89", "sql injection", source_id="cwe")
    cves = [
        chunk(f"CVE-2026-{i:04d}", "a product flaw", source_id="vulns")
        for i in range(retriever.NEIGHBOR_CANDIDATES + 10)
    ]
    patterns = [
        chunk(f"CAPEC-{i}", "capec sql injection pattern", source_id="capec") for i in (7, 66)
    ]
    edges = [
        Edge(src_id=c.native_id, rel="has_weakness", dst_id="CWE-89", origin="vulns") for c in cves
    ]
    edges += [
        Edge(src_id=p.native_id, rel="related_weakness", dst_id="CWE-89", origin="capec")
        for p in patterns
    ]
    kb = small_kb([weakness, *cves, *patterns], edges, limit=20)

    found = await kb.retrieve("Which CAPEC patterns relate to CWE-89 sql injection?")

    graph = [r.chunk.native_id for r in found if r.via == "graph"]
    assert set(graph[:2]) == {"CAPEC-7", "CAPEC-66"}


def weakness_with_cves_and_patterns() -> KnowledgeBase:
    """CWE-89 with CVEs that match SQL injection questions better than its CAPEC patterns do."""
    weakness = chunk("CWE-89", "sql injection", source_id="cwe")
    cves = [
        chunk(f"CVE-2026-{i:04d}", "which sql injection patterns relate", source_id="vulns")
        for i in range(20)
    ]
    patterns = [chunk(f"CAPEC-{i}", "an attack", source_id="capec") for i in (7, 66)]
    edges = [
        Edge(src_id=c.native_id, rel="has_weakness", dst_id="CWE-89", origin="vulns") for c in cves
    ]
    edges += [
        Edge(src_id=p.native_id, rel="related_weakness", dst_id="CWE-89", origin="capec")
        for p in patterns
    ]
    return small_kb([weakness, *cves, *patterns], edges, limit=20)


async def test_a_question_asking_for_one_source_gets_only_its_neighbors():
    kb = weakness_with_cves_and_patterns()

    found = await kb.retrieve("Which CAPEC patterns relate to CWE-89 sql injection?")

    assert [r.chunk.native_id for r in found if r.via == "graph"] == ["CAPEC-7", "CAPEC-66"]
    assert "CWE-89" in [r.chunk.native_id for r in found if r.via == "id"]


@pytest.mark.parametrize(
    "question",
    [
        # An ID of a source doesn't ask for that source: CWE-89 is no request for CWEs.
        "Which patterns relate to CWE-89 sql injection?",
        # Nor does a singular: it says what the unit is, not which units to list.
        "What kind of weakness is CWE-89, and which sql injection patterns relate?",
        # A source without neighbors here changes nothing.
        "Which ATLAS techniques relate to CWE-89 sql injection?",
    ],
)
async def test_without_an_asked_for_source_among_them_all_neighbors_compete(question):
    kb = weakness_with_cves_and_patterns()

    found = await kb.retrieve(question)

    graph = [r.chunk for r in found if r.via == "graph"]
    assert {c.source_id for c in graph} == {"vulns"}
    assert len(graph) == retriever.MAX_NEIGHBORS


async def test_the_section_cap_counts_language_copies_once():
    # Both copies of a section score alike, and later sections score higher, so the ranking
    # interleaves languages: en3, de3, en2, de2, ...
    words = ["risikomanagement", "pflichten", "systeme", "dokumentation"]
    sections = [
        chunk(
            "AI Act Art. 9(1)",
            " ".join(words[: i + 1]),
            source_id="eu-ai-act",
            language=lang,
            unit_key="art_9.1",
            chunk_index=i,
        )
        for i in range(4)
        for lang in ("en", "de")
    ]
    kb = small_kb(sections, [], min_score=100.0)

    found = await kb.retrieve(
        "Was regelt Art. 9 Abs. 1 zu Risikomanagement, Pflichten, Systeme, Dokumentation?"
    )

    # Counting copies would keep en3, de3, en2 and leave two German sections after the swap.
    assert [(r.chunk.language, r.chunk.chunk_index) for r in found] == [
        ("de", 3),
        ("de", 2),
        ("de", 1),
    ]


def surveillance_kb() -> KnowledgeBase:
    # English AI Act text shares the question's words; the German-only KI-MIG doesn't.
    articles = [
        chunk(
            f"AI Act Art. 74({i})",
            "which authority is the market surveillance authority",
            source_id="eu-ai-act",
        )
        for i in range(1, 5)
    ]
    section = chunk(
        "KI-MIG § 2 Abs. 1",
        "KI-MIG Marktüberwachungsbehörde ist die Bundesnetzagentur",
        source_id="ki-mig",
        language="de",
    )
    return small_kb([*articles, section], [], candidates=4, limit=3)


async def test_a_question_naming_an_act_finds_its_text_over_another_acts():
    found = await surveillance_kb().retrieve(
        "Which authority is the market surveillance authority under the KI-MIG?"
    )

    assert len(found) == 3
    assert "KI-MIG § 2 Abs. 1" in [r.chunk.native_id for r in found]


async def test_a_question_naming_no_act_is_searched_once():
    found = await surveillance_kb().retrieve(
        "Which authority is the market surveillance authority?"
    )

    assert {r.chunk.source_id for r in found} == {"eu-ai-act"}


async def test_search_hits_add_no_sections_past_a_named_units_cap():
    sections = [
        chunk("LLM06:2026", "llm06:2026 unbounded consumption", source_id="owasp-llm-2026",
              chunk_index=i)
        for i in range(5)
    ]  # fmt: skip
    mitigation = chunk("AML.M0036", "atlas mitigation")
    kb = small_kb([*sections, mitigation], [], limit=retriever.MAX_PER_UNIT + 1)

    found = await kb.retrieve("Which ATLAS mitigation addresses LLM06:2026 unbounded consumption?")

    assert [r.chunk.native_id for r in found] == ["LLM06:2026"] * retriever.MAX_PER_UNIT + [
        "AML.M0036"
    ]


def test_the_knowledge_base_returns_only_what_the_answer_sees():
    settings = Settings(retrieval_top_k=3)
    kb = retriever.knowledge_base(
        settings, QdrantClient(":memory:"), "kb", FakeEmbedder(), FakeSparseEmbedder(),
        FakeReranker(), EdgeGraph([]),
    )  # fmt: skip

    assert kb.limit == settings.retrieval_top_k


def counters_kb() -> KnowledgeBase:
    # The ATT&CK technique and other ATT&CK units share the question's words; the D3FEND
    # technique countering it shares one, so search ranks it past the limit.
    technique = chunk(
        "T1566.002", "spearphishing link attacks counter file integrity", source_id="attack"
    )
    others = [
        chunk(f"T1566.00{i}", "spearphishing link attacks", source_id="attack") for i in (1, 3, 4)
    ]
    countermeasure = chunk("D3-FIM", "monitoring", source_id="d3fend")
    edge = Edge(src_id="D3-FIM", rel="counters", dst_id="T1566.002", origin="d3fend")
    return small_kb([technique, *others, countermeasure], [edge], limit=3)


async def test_a_link_to_another_sources_hit_keeps_a_place():
    found = await counters_kb().retrieve(
        "Can file integrity monitoring counter spearphishing link attacks?"
    )

    ids = [r.chunk.native_id for r in found]
    assert len(ids) == 3
    assert {"T1566.002", "D3-FIM"} <= set(ids)


async def test_a_question_not_about_related_items_keeps_the_search_ranking():
    found = await counters_kb().retrieve("spearphishing attacks file integrity monitoring")

    assert "D3-FIM" not in [r.chunk.native_id for r in found]


async def test_a_linked_units_place_never_comes_from_its_partner():
    # The ATT&CK technique is the last kept passage: the D3FEND technique's place must come
    # from the unrelated passage above it.
    noise = [
        chunk(
            f"T1000.00{i}",
            "can file integrity counter spearphishing link attacks",
            source_id="attack",
        )
        for i in (1, 2)
    ]
    technique = chunk("T1566.002", "spearphishing link attacks", source_id="attack")
    countermeasure = chunk("D3-FIM", "monitoring", source_id="d3fend")
    edge = Edge(src_id="D3-FIM", rel="counters", dst_id="T1566.002", origin="d3fend")
    kb = small_kb([*noise, technique, countermeasure], [edge], limit=3)

    found = await kb.retrieve("Can file integrity monitoring counter spearphishing link attacks?")

    ids = [r.chunk.native_id for r in found]
    assert len(ids) == 3
    assert {"T1566.002", "D3-FIM"} <= set(ids)


async def test_a_linked_unit_the_question_names_by_title_beats_a_better_scored_one():
    question = (
        "How does Application Protocol Command Analysis relate to attackers who use stolen web "
        "session cookies to access applications?"
    )
    # Scores (shared words): noise > technique > filler > CAPEC pattern > D3FEND technique.
    noise = chunk("T1000", question.lower(), source_id="attack", title="noise")
    technique = chunk(
        "T1550.004",
        "relate attackers who use stolen web session cookies to access applications",
        source_id="attack",
        title="Web Session Cookie",
    )
    filler = chunk(
        "T1001",
        "how does relate attackers who use stolen web session cookies",
        source_id="attack",
        title="filler",
    )
    pattern = chunk(
        "CAPEC-60",
        "attackers use stolen web session cookies",
        source_id="capec",
        title="Reusing Session IDs",
    )
    countermeasure = chunk(
        "D3-APCA",
        "remote commands",
        source_id="d3fend",
        title="Application Protocol Command Analysis",
    )
    edges = [
        Edge(src_id="D3-APCA", rel="counters", dst_id="T1550.004", origin="d3fend"),
        Edge(src_id="CAPEC-60", rel="related_attack_pattern", dst_id="T1550.004", origin="capec"),
    ]
    kb = small_kb([noise, technique, filler, pattern, countermeasure], edges, limit=3)

    found = await kb.retrieve(question)

    ids = [r.chunk.native_id for r in found]
    assert "D3-APCA" in ids and "CAPEC-60" not in ids
