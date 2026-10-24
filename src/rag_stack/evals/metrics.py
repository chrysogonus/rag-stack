from collections.abc import Sequence


def recall_at_k(ranked: Sequence[str], gold: Sequence[str], k: int = 10) -> float:
    """Share of gold IDs among the first k distinct retrieved IDs."""
    top = list(dict.fromkeys(ranked))[:k]
    return sum(g in top for g in gold) / len(gold)


def mrr(ranked: Sequence[str], gold: Sequence[str]) -> float:
    """1 / rank of the first gold ID among the distinct retrieved IDs, 0 if none."""
    for rank, item in enumerate(dict.fromkeys(ranked), start=1):
        if item in gold:
            return 1 / rank
    return 0.0


def citation_precision(cited: Sequence[str], gold: Sequence[str]) -> float:
    """Share of cited IDs that are gold IDs. Citing nothing in an answer scores 0."""
    if not cited:
        return 0.0
    return sum(c in gold for c in cited) / len(cited)


def mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None
