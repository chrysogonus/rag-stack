from collections import defaultdict
from collections.abc import Collection, Iterable

import psycopg

from rag_stack.ingestion.models import Edge


def replace_edges(
    database_url: str, kb: str, generation: str, origin: str, edges: Iterable[Edge]
) -> None:
    """Swap one source's edges within one index generation, in a single transaction. `kb` is
    the knowledge base (the index alias): packs sharing the table keep their own edges."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM kb_edges WHERE kb = %s AND generation = %s AND origin = %s",
            (kb, generation, origin),
        )
        cur.executemany(
            "INSERT INTO kb_edges (kb, generation, src_id, rel, dst_id, origin) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            [(kb, generation, e.src_id, e.rel, e.dst_id, e.origin) for e in edges],
        )


def copy_edges(database_url: str, kb: str, source: str, target: str) -> int:
    """Copy every edge of one generation into another; returns how many were copied."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO kb_edges (kb, generation, src_id, rel, dst_id, origin) "
            "SELECT kb, %s, src_id, rel, dst_id, origin FROM kb_edges "
            "WHERE kb = %s AND generation = %s ORDER BY seq ON CONFLICT DO NOTHING",
            (target, kb, source),
        )
        return cur.rowcount


def delete_edge_generations(database_url: str, kb: str, keep: Collection[str]) -> None:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM kb_edges WHERE kb = %s AND generation <> ALL(%s)", (kb, list(keep))
        )


def load_edges(database_url: str, kb: str, generation: str) -> list[Edge]:
    """A generation's edges in the order they were written: retrieval caps neighbors in it."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT src_id, rel, dst_id, origin FROM kb_edges "
            "WHERE kb = %s AND generation = %s ORDER BY seq",
            (kb, generation),
        )
        return [Edge(src_id=s, rel=r, dst_id=d, origin=o) for s, r, d, o in cur.fetchall()]


class EdgeGraph:
    """The edge table held in memory (a few thousand rows) for 1-hop lookups.

    shortcut: loaded once at startup, so a re-index or promotion needs an API restart (`make
    refresh` does it); query Postgres per request if the table grows large."""

    def __init__(self, edges: Iterable[Edge]) -> None:
        self._by_node: dict[str, list[Edge]] = defaultdict(list)
        for edge in edges:
            self._by_node[edge.src_id].append(edge)
            self._by_node[edge.dst_id].append(edge)

    def edges(self, node: str, rels: Collection[str] | None = None) -> list[Edge]:
        """Edges touching a node in either direction, optionally only the given relations."""
        return [e for e in self._by_node.get(node, []) if rels is None or e.rel in rels]

    def neighbors(self, node: str, rels: Collection[str] | None = None) -> list[str]:
        """IDs one hop away in either direction, optionally only over the given relations."""
        others = (e.dst_id if e.src_id == node else e.src_id for e in self.edges(node, rels))
        return list(dict.fromkeys(others))
