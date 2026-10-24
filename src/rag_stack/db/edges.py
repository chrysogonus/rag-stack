from collections import defaultdict
from collections.abc import Collection, Iterable

import psycopg

from rag_stack.ingestion.models import Edge


def replace_edges(database_url: str, origin: str, edges: Iterable[Edge]) -> None:
    """Swap one source's edges in a single transaction."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM kb_edges WHERE origin = %s", (origin,))
        cur.executemany(
            "INSERT INTO kb_edges (src_id, rel, dst_id, origin) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            [(e.src_id, e.rel, e.dst_id, e.origin) for e in edges],
        )


def load_edges(database_url: str) -> list[Edge]:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT src_id, rel, dst_id, origin FROM kb_edges")
        return [Edge(src_id=s, rel=r, dst_id=d, origin=o) for s, r, d, o in cur.fetchall()]


class EdgeGraph:
    """The edge table held in memory (a few thousand rows) for 1-hop lookups.

    shortcut: loaded once at startup, so a re-index needs an API restart; query Postgres
    per request if the table grows large or changes while serving."""

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
