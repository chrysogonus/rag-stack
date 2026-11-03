import re
from collections.abc import Iterable, Mapping

# Common function words; a pack adds the words of its domain (Language.extra_words).
WORDS = {
    "de": {
        "der", "die", "das", "und", "ist", "nicht", "welche", "welcher", "welches", "wie", "was",
        "wer", "für", "mit", "ein", "eine", "einen", "dem", "den", "des", "auf", "zu", "im", "nach",
        "gibt", "es", "sind", "werden", "muss", "müssen", "gilt", "regelt", "nennt", "bei", "oder",
        "über", "gegen", "ich", "sie", "wir",
    },
    "en": {
        "the", "and", "is", "not", "which", "what", "how", "who", "for", "with", "a", "an", "of",
        "to", "in", "on", "does", "do", "are", "must", "there", "say", "says", "about", "against",
        "or", "by", "i", "you", "we", "list", "explain",
    },
}  # fmt: skip
# Letters only one of the languages has; each counts twice.
LETTERS = {"de": "äöüß"}


def detect_language(text: str, languages: Mapping[str, Iterable[str]]) -> str:
    """The language among `languages` (code → the pack's extra words) whose words and letters the
    text has most of; a tie goes to the first."""
    lowered = text.lower()
    words = re.findall(r"[^\W\d_]+", lowered)

    def score(code: str) -> int:
        known = WORDS.get(code, set()) | set(languages[code])
        letters = sum(lowered.count(letter) for letter in LETTERS.get(code, ""))
        return sum(w in known for w in words) + 2 * letters

    return max(languages, key=score)
