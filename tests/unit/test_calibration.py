import json

import pytest
from fakes.embeddings import chunk
from fakes.llm import FakeChatModel

from rag_stack.config import Settings
from rag_stack.evals import calibration
from rag_stack.evals.harness import CATEGORIES, DATASET, judge, load_cases
from rag_stack.retrieval.retriever import Retrieved

RESULTS = {r["id"]: r for r in json.loads((DATASET / "results.json").read_text())}
CASES = {c["id"]: c for c in load_cases()}


class Replay:
    """Retrieves, for each golden question, the IDs the saved eval run retrieved."""

    def __init__(self, shift: bool = False) -> None:
        self.shift = shift
        self.by_question = {
            (CASES[i]["question"], CASES[i].get("follow_up_of", "")): r["retrieved"]
            for i, r in RESULTS.items()
        }

    async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
        ids = self.by_question[(query, context)]
        ids = ids[1:] + ids[:1] if self.shift else ids
        return [Retrieved(chunk(i, f"Text of {i}"), 1.0, "hybrid") for i in ids]

    async def catalog(self) -> list[str]:
        return []


@pytest.fixture
def sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration, "LABELS", tmp_path / "judge_labels.jsonl")
    return calibration.LABELS


@pytest.mark.anyio
async def test_the_sheet_samples_both_bots_per_category_without_judge_scores(sheet):
    settings = Settings()
    assert await calibration.write_sheet(settings, Replay()) == 0

    rows = [json.loads(line) for line in sheet.read_text().splitlines()]
    assert len(rows) == 5 * len(CATEGORIES)
    assert sum(r["id"].endswith(":baseline") for r in rows) == 2 * len(CATEGORIES)
    for row in rows:
        assert row["correctness"] is None
        # Nothing of the judge's verdict, which would anchor the label.
        assert set(row) == {
            "id", "previous_question", "question", "key_facts", "answer", "sources", "correctness"
        }  # fmt: skip
        assert "\n---\n**" not in row["answer"]  # the footer is cut, as the judge sees it
        case_id, kind = row["id"].split(":")
        if kind == "rag":
            ids = [s["native_id"] for s in row["sources"]]
            assert ids == RESULTS[case_id]["retrieved"][: settings.retrieval_top_k]
        else:
            assert row["sources"] is None  # the baseline answers without sources
    # Labels are never overwritten by a new sample.
    assert await calibration.write_sheet(settings, Replay()) == 1


@pytest.mark.anyio
async def test_the_sheet_is_refused_when_retrieval_no_longer_matches_the_run(sheet):
    with pytest.raises(ValueError, match="retrieval changed"):
        await calibration.write_sheet(Settings(), Replay(shift=True))
    assert not sheet.exists()


@pytest.mark.anyio
async def test_the_judge_gets_the_same_payload_in_calibration_as_in_the_eval():
    case = {"id": "x", "question": "Q?", "key_facts": ["F"], "follow_up_of": "P?"}
    seen = [chunk("AML.T0051", "Long text " * 400, meta={"relation": "AML.M0019 mitigates it"})]
    verdict = '{"correctness": 5, "faithfulness": 5}'
    eval_judge, sheet_judge = FakeChatModel(verdict), FakeChatModel(verdict)

    await judge(eval_judge, case, "A", [c.model_dump() for c in seen])

    class One:
        async def retrieve(self, query: str, context: str = "") -> list[Retrieved]:
            return [Retrieved(c, 1.0, "id") for c in seen]

        async def catalog(self) -> list[str]:
            return []

    stored = await calibration.passages(One(), case, {"id": "x", "retrieved": ["AML.T0051"]}, 8)
    await judge(sheet_judge, case, "A", json.loads(json.dumps(stored)))
    assert sheet_judge.calls == eval_judge.calls


@pytest.mark.anyio
async def test_agreement_judges_the_labeled_answers_again(sheet, capsys):
    passage = [{"native_id": "AML.T0051", "meta": {"relation": None}, "text": "T"}]
    rows = [
        {"id": "a:rag", "previous_question": None, "question": "Q?", "key_facts": ["F"],
         "answer": "A", "sources": passage, "correctness": 5},
        {"id": "b:baseline", "previous_question": "P?", "question": "Q?", "key_facts": ["F"],
         "answer": "B", "sources": None, "correctness": 2},
        {"id": "c:rag", "previous_question": None, "question": "Q?", "key_facts": ["F"],
         "answer": "C", "sources": passage, "correctness": None},
    ]  # fmt: skip
    sheet.write_text("".join(json.dumps(r) + "\n" for r in rows))
    judge = FakeChatModel(*(f'{{"correctness": {v}, "faithfulness": null}}' for v in (5, 5)))

    assert await calibration.agreement(Settings(), judge) == 0

    assert len(judge.calls) == 2  # the unlabeled answer is skipped
    sent = [json.loads(c["messages"][0]["content"]) for c in judge.calls]
    assert {s["answer"] for s in sent} == {"A", "B"}
    # The RAG answer is judged with its passages, the baseline answer without.
    assert {s["answer"]: s["sources"] for s in sent} == {
        "A": [{"id": "AML.T0051", "relation": None, "text": "T"}],
        "B": None,
    }
    assert any(s.get("previous_question") == "P?" for s in sent)
    out = capsys.readouterr().out
    assert "exact 0.50" in out and "within one point 0.50" in out
    assert "mean judge minus human +1.50 points" in out and "+3 b:baseline" in out


@pytest.mark.anyio
async def test_labels_outside_the_rubric_scale_are_refused(sheet):
    row = {"id": "a:rag", "previous_question": None, "question": "Q?", "key_facts": ["F"],
           "answer": "A", "sources": None, "correctness": 7}  # fmt: skip
    sheet.write_text(json.dumps(row) + "\n")

    with pytest.raises(ValueError, match="1-5"):
        await calibration.agreement(Settings(), FakeChatModel())
