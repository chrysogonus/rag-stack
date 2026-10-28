from collections.abc import Collection, Iterable

from rag_stack.db import edges
from rag_stack.ingestion.models import Edge


class FakeEdgeStore:
    """The kb_edges table in memory, per generation, with the functions of `rag_stack.db.edges`."""

    def __init__(self) -> None:
        self.rows: dict[str, list[Edge]] = {}

    def install(self, monkeypatch) -> "FakeEdgeStore":
        for name in ("replace_edges", "copy_edges", "delete_edge_generations", "load_edges"):
            monkeypatch.setattr(edges, name, getattr(self, name))
        return self

    def replace_edges(self, url: str, generation: str, origin: str, new: Iterable[Edge]) -> None:
        kept = [e for e in self.rows.get(generation, []) if e.origin != origin]
        self.rows[generation] = kept + list(new)

    def copy_edges(self, url: str, source: str, target: str) -> int:
        copied = list(self.rows.get(source, []))
        self.rows[target] = self.rows.get(target, []) + copied
        return len(copied)

    def delete_edge_generations(self, url: str, keep: Collection[str]) -> None:
        self.rows = {g: rows for g, rows in self.rows.items() if g in keep}

    def load_edges(self, url: str, generation: str) -> list[Edge]:
        return list(self.rows.get(generation, []))
