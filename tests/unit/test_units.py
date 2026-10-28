import pytest
from fakes.embeddings import chunk

from rag_stack.config import Settings
from rag_stack.db.edges import EdgeGraph
from rag_stack.evals import units
from rag_stack.ingestion.models import Edge
from rag_stack.ingestion.pipeline import write_processed
from rag_stack.retrieval.retriever import Retrieved

EDGE = Edge(src_id="AML.M0001", rel="mitigates", dst_id="AML.T0001", origin="atlas")


class Scripted:
    """Answers each question with the scripted IDs; nothing for any other question."""

    def __init__(self, answers: dict[str, list[str]]) -> None:
        self.answers = answers
        self.asked: list[str] = []
        self.graph = EdgeGraph([EDGE])

    async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
        self.asked.append(query)
        return [Retrieved(chunk(i), 1.0, "id") for i in self.answers.get(query, [])]


@pytest.fixture
def settings(tmp_path) -> Settings:
    chunks = [
        chunk("AML.T0001", title="Search Victim Research"),
        chunk("AML.M0001", title="Limit Model Artifact Release"),
        chunk("AML.TA0001", title="AML.TA0001 names an ID"),
        chunk("ATLAS Tactics", meta={"kind": "overview"}),
    ]
    write_processed(tmp_path / "processed/atlas/v1", chunks, [EDGE], "sha")
    (tmp_path / "processed/atlas/LATEST").write_text("v1")
    return Settings(data_dir=str(tmp_path))


@pytest.mark.anyio
async def test_units_are_asked_by_id_title_and_edge(settings, capsys):
    kb = Scripted(
        {
            "What is AML.T0001?": ["AML.T0001"],
            "What is AML.M0001?": ["AML.M0001"],
            "What is AML.TA0001?": ["AML.TA0001"],
            "Search Victim Research": ["AML.M0001", "AML.T0001"],
            "Which units are related to AML.M0001?": ["AML.M0001", "AML.T0001"],
        }
    )

    assert await units.main(settings, 10, kb) == 0  # type: ignore[arg-type]
    # No overview, and no title search for a title naming an ID; the title miss is only a score.
    assert sorted(kb.asked) == [
        "Limit Model Artifact Release",
        "Search Victim Research",
        "What is AML.M0001?",
        "What is AML.T0001?",
        "What is AML.TA0001?",
        "Which units are related to AML.M0001?",
    ]
    out = capsys.readouterr().out
    assert "title:\n  atlas                   1 / 2    0.500" in out
    assert "miss title    atlas                AML.M0001" in out


@pytest.mark.anyio
async def test_an_id_not_ranking_its_own_unit_first_fails(settings, capsys):
    kb = Scripted({"What is AML.T0001?": ["AML.M0001", "AML.T0001"]})

    assert await units.main(settings, 10, kb) == 1  # type: ignore[arg-type]
    assert "miss id       atlas                AML.T0001" in capsys.readouterr().out
