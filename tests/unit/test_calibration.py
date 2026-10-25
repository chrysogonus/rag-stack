import json

import pytest
from fakes.llm import FakeChatModel

from rag_stack.config import Settings
from rag_stack.evals import calibration
from rag_stack.evals.harness import CATEGORIES, DATASET


@pytest.fixture
def sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(calibration, "LABELS", tmp_path / "judge_labels.jsonl")
    return calibration.LABELS


def test_the_sheet_samples_both_bots_per_category_without_judge_scores(sheet):
    assert calibration.write_sheet() == 0

    rows = [json.loads(line) for line in sheet.read_text().splitlines()]
    results = {r["id"]: r for r in json.loads((DATASET / "results.json").read_text())}
    assert len(rows) == 5 * len(CATEGORIES)
    assert sum(r["id"].endswith(":baseline") for r in rows) == 2 * len(CATEGORIES)
    for row in rows:
        assert row["correctness"] is None
        # Nothing of the judge's verdict, which would anchor the label.
        assert set(row) == {
            "id", "previous_question", "question", "key_facts", "answer", "correctness"
        }  # fmt: skip
        assert "\n---\n**" not in row["answer"]  # the footer is cut, as the judge sees it
        assert row["id"].split(":")[0] in results
    # Labels are never overwritten by a new sample.
    assert calibration.write_sheet() == 1


@pytest.mark.anyio
async def test_agreement_judges_the_labeled_answers_again(sheet, capsys):
    rows = [
        {"id": "a:rag", "previous_question": None, "question": "Q?", "key_facts": ["F"],
         "answer": "A", "correctness": 5},
        {"id": "b:baseline", "previous_question": "P?", "question": "Q?", "key_facts": ["F"],
         "answer": "B", "correctness": 2},
        {"id": "c:rag", "previous_question": None, "question": "Q?", "key_facts": ["F"],
         "answer": "C", "correctness": None},
    ]  # fmt: skip
    sheet.write_text("".join(json.dumps(r) + "\n" for r in rows))
    judge = FakeChatModel(*(f'{{"correctness": {v}, "faithfulness": null}}' for v in (5, 5)))

    assert await calibration.agreement(Settings(), judge) == 0

    assert len(judge.calls) == 2  # the unlabeled answer is skipped
    sent = [json.loads(c["messages"][0]["content"]) for c in judge.calls]
    assert {s["answer"] for s in sent} == {"A", "B"}
    assert any(s.get("previous_question") == "P?" for s in sent)
    out = capsys.readouterr().out
    assert "exact 0.50" in out and "within one point 0.50" in out
    assert "mean judge minus human +1.50 points" in out and "+3 b:baseline" in out


@pytest.mark.anyio
async def test_labels_outside_the_rubric_scale_are_refused(sheet):
    row = {"id": "a:rag", "previous_question": None, "question": "Q?", "key_facts": ["F"],
           "answer": "A", "correctness": 7}  # fmt: skip
    sheet.write_text(json.dumps(row) + "\n")

    with pytest.raises(ValueError, match="1-5"):
        await calibration.agreement(Settings(), FakeChatModel())
