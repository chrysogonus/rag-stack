from collections.abc import Hashable, Sequence


def rrf[T: Hashable](rankings: Sequence[Sequence[T]], k: int = 60) -> list[T]:
    """Reciprocal rank fusion: score(d) = sum over rankings of 1 / (k + rank(d)), rank from 1."""
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item: -scores[item])
