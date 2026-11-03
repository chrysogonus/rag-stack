"""The edge table against the real Postgres (`make e2e` migrates it first)."""

import pytest

from rag_stack.config import Settings
from rag_stack.db import edges
from rag_stack.ingestion.models import Edge

pytestmark = pytest.mark.e2e

EDGE = Edge(src_id="NOTE-1", rel="refers_to", dst_id="NOTE-2", origin="notes")


def test_knowledge_bases_sharing_postgres_keep_their_own_edges():
    url = Settings().database_url
    mine, other = "e2e_kb_mine", "e2e_kb_other"
    try:
        edges.replace_edges(url, mine, "g1", "notes", [EDGE])
        edges.replace_edges(url, other, "g1", "notes", [EDGE])

        assert edges.copy_edges(url, mine, "g1", "g2") == 1
        edges.delete_edge_generations(url, mine, keep=["g2"])

        assert edges.load_edges(url, mine, "g1") == []
        assert edges.load_edges(url, mine, "g2") == [EDGE]
        # Another knowledge base's generation of the same name survives a cleanup of mine.
        assert edges.load_edges(url, other, "g1") == [EDGE]
    finally:
        edges.delete_edge_generations(url, mine, keep=[])
        edges.delete_edge_generations(url, other, keep=[])


def test_edges_load_in_the_order_they_were_written():
    # The retriever caps a unit's neighbors in edge order (a CWE has hundreds of CVEs), so the
    # order is part of retrieval: the parser's, not whatever plan Postgres picks.
    url, kb = Settings().database_url, "e2e_kb_order"
    written = [
        Edge(src_id=f"NOTE-{n}", rel="refers_to", dst_id="NOTE-0", origin="notes")
        for n in (3, 1, 2)
    ]
    try:
        edges.replace_edges(url, kb, "g1", "notes", written)
        edges.copy_edges(url, kb, "g1", "g2")

        assert edges.load_edges(url, kb, "g1") == written
        assert edges.load_edges(url, kb, "g2") == written
    finally:
        edges.delete_edge_generations(url, kb, keep=[])
