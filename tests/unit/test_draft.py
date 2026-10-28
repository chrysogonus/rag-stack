import json
from pathlib import Path

import pytest
from fakes.embeddings import chunk
from fakes.llm import FakeChatModel

from rag_stack.config import Settings
from rag_stack.evals import draft
from rag_stack.ingestion.models import Edge
from rag_stack.ingestion.pipeline import write_processed
from rag_stack.llm.base import TextDelta

DRAFTED = '{"question": "What does the new technique do?", "key_facts": ["It does X"]}'


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """A processed corpus: ATLAS with one unit the golden set already asks about (AML.T0051),
    an OWASP entry mapped to a new ATLAS technique, and a German KI-MIG section."""
    monkeypatch.setattr(draft, "DRAFTS", tmp_path / "drafts.jsonl")
    settings = Settings(data_dir=str(tmp_path))
    corpus = {
        "atlas": (
            [
                chunk("AML.T0051"),
                chunk("AML.T9990", "New technique."),
                chunk("AML.T9990", "Its second part.", chunk_index=1),
                chunk("ATLAS Tactics", meta={"kind": "overview"}),
            ],
            [],
        ),
        "owasp-llm-2026": (
            [chunk("LLM99:2026", "A new risk.", source_id="owasp-llm-2026")],
            [
                Edge(src_id="LLM99:2026", rel="maps_to", dst_id="AML.T9990", origin="x"),
                Edge(src_id="LLM99:2026", rel="maps_to", dst_id="CWE-1", origin="x"),
            ],
        ),
        "ki-mig": ([chunk("KI-MIG § 99", "Text.", source_id="ki-mig", language="de")], []),
        "eu-ai-act": (
            [
                chunk(
                    "AI Act Art. 99(1)",
                    source_id="eu-ai-act",
                    language="de",
                    parent_ids=["AI Act Art. 99"],
                )
            ],
            [],
        ),
    }
    for source_id, (chunks, edges) in corpus.items():
        write_processed(tmp_path / "processed" / source_id / "v1", chunks, edges, "sha")
        (tmp_path / "processed" / source_id / "LATEST").write_text("v1")
    return settings


def ids(pool):
    return [[u.native_id for u in units] for units, _ in pool]


def test_candidates_are_units_nobody_asked_about_yet(settings):
    assert ids(draft.candidates(settings, "atlas", "paraphrase")) == [["AML.T9990"]]
    assert ids(draft.candidates(settings, "ki-mig", "id-exact")) == [["KI-MIG § 99"]]
    assert ids(draft.candidates(settings, "ki-mig", "german-legal")) == [["KI-MIG § 99"]]


def test_units_named_by_a_golden_question_or_its_key_facts_count_as_asked(settings, monkeypatch):
    overview = {
        "category": "list",
        "question": "List the top 10, and what does Article 99 say?",
        "gold_ids": ["OWASP LLM Top 10 2026"],
        "key_facts": ["LLM99:2026 A new risk"],
    }
    monkeypatch.setattr(draft, "load_cases", lambda: [overview])

    # LLM99:2026 is only in a key fact; Art. 99(1) only under the named article.
    assert draft.candidates(settings, "owasp-llm-2026", "paraphrase") == []
    assert draft.candidates(settings, "owasp-llm-2026", "cross-source") == []
    assert draft.candidates(settings, "eu-ai-act", "german-legal") == []


def test_cross_source_candidates_are_edges_between_indexed_units_with_their_relation(settings):
    pool = draft.candidates(settings, "owasp-llm-2026", "cross-source")

    # The edge to CWE-1 has no unit to ask about.
    assert ids(pool) == [["LLM99:2026", "AML.T9990"]]
    assert pool[0][1] == "Relationship: LLM99:2026 maps_to AML.T9990"


def test_categories_that_dont_fit_the_source_are_refused(settings):
    with pytest.raises(ValueError, match="cve questions don't fit atlas"):
        draft.candidates(settings, "atlas", "cve")
    with pytest.raises(ValueError, match="not ingested"):
        draft.candidates(settings, "vulns", "cve")


@pytest.mark.anyio
async def test_drafts_are_appended_for_review_and_their_units_not_drafted_again(settings, capsys):
    llm = FakeChatModel(f"Sure: {DRAFTED}")

    assert await draft.main(settings, "atlas", "paraphrase", 3, llm=llm) == 0

    [written] = [json.loads(line) for line in draft.DRAFTS.read_text().splitlines()]
    assert written == {
        "id": "draft-paraphrase-aml-t9990",
        "category": "paraphrase",
        "split": "test",
        "language": "en",
        "question": "What does the new technique do?",
        "gold_ids": ["AML.T9990"],
        "key_facts": ["It does X"],
        "needs_review": True,
    }
    assert "New technique." in llm.calls[0]["messages"][0]["content"]
    assert "without naming its id" in llm.calls[0]["instructions"]
    assert "1 of 1 drafts appended" in capsys.readouterr().out
    # The drafted unit counts as asked: a second run finds nothing new.
    assert await draft.main(settings, "atlas", "paraphrase", 3, llm=llm) == 1


@pytest.mark.anyio
async def test_unusable_drafts_are_dropped(settings):
    leaks_id = '{"question": "What is AML.T9990?", "key_facts": ["X"]}'

    for reply in ("not json", '{"question": "Q?", "key_facts": []}', leaks_id):
        assert await draft.main(settings, "atlas", "paraphrase", 1, llm=FakeChatModel(reply)) == 1
    assert draft.DRAFTS.read_text() == ""


@pytest.mark.anyio
async def test_a_failed_request_keeps_the_other_drafts(settings, capsys):
    class FailsOnce(FakeChatModel):
        async def stream(self, messages, *, instructions, max_output_tokens):
            if not self.calls:
                self.calls.append({})
                raise TimeoutError("provider timed out")
                yield TextDelta("")  # unreachable: makes this an async generator
            async for event in super().stream(
                messages, instructions=instructions, max_output_tokens=max_output_tokens
            ):
                yield event

    two_units = [chunk("AML.T9991", "One."), chunk("AML.T9992", "Two.")]
    write_processed(Path(settings.data_dir) / "processed/atlas/v1", two_units, [], "sha")

    assert await draft.main(settings, "atlas", "id-exact", 2, llm=FailsOnce(DRAFTED)) == 1

    assert len(draft.DRAFTS.read_text().splitlines()) == 1
    assert "1 of 2 requests failed, e.g. TimeoutError('provider timed out')" in (
        capsys.readouterr().out
    )
