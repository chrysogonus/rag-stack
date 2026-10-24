from rag_stack.agent.prompts import build_input
from rag_stack.llm.base import Message


def turns(n: int) -> list[Message]:
    messages: list[Message] = []
    for i in range(n):
        messages.append({"role": "user", "content": f"q{i}"})
        messages.append({"role": "assistant", "content": f"a{i}"})
    return messages


def test_keeps_short_history_unchanged():
    history = [*turns(2), {"role": "user", "content": "q2"}]
    assert build_input(history, max_messages=20) == history


def test_trims_to_most_recent_messages():
    history = [*turns(5), {"role": "user", "content": "q5"}]
    assert [m["content"] for m in build_input(history, max_messages=5)] == [
        "q3",
        "a3",
        "q4",
        "a4",
        "q5",
    ]


def test_trimmed_history_starts_on_a_user_turn():
    history = [*turns(5), {"role": "user", "content": "q5"}]
    trimmed = build_input(history, max_messages=4)
    assert trimmed[0]["role"] == "user"
    assert [m["content"] for m in trimmed] == ["q4", "a4", "q5"]


def test_empty_history():
    assert build_input([], max_messages=4) == []
