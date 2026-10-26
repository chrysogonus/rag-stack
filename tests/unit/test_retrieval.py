from pathlib import Path

import pytest
from fakes.embeddings import FakeEmbedder, FakeReranker, FakeSparseEmbedder, chunk
from qdrant_client import QdrantClient

from rag_stack.db.edges import EdgeGraph
from rag_stack.ingestion.models import Edge, Snapshot
from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS, SOURCES
from rag_stack.ingestion.sources import atlas, eu_law
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
        ("Wer ist nach § 2 Abs. 3 KI-MIG zuständig?", ["KI-MIG § 2 Abs. 3"]),
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
    assert set(ids) == {"AI Act Art. 50(1)", "AI Act Art. 50(2)", "AI Act Art. 50(3)"}


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


async def test_a_named_unit_keeps_only_its_best_sections_so_related_units_fit():
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

    found = await kb.retrieve("Which ASI risks map to LLM01:2026?")

    assert [r.chunk.native_id for r in found] == ["LLM01:2026"] * 3 + ["ASI01"]


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
