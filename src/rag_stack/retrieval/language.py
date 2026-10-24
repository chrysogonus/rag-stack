import re

GERMAN = {
    "der", "die", "das", "und", "ist", "nicht", "welche", "welcher", "welches", "wie", "was",
    "wer", "für", "mit", "ein", "eine", "einen", "dem", "den", "des", "auf", "zu", "im", "nach",
    "gibt", "es", "sind", "werden", "muss", "müssen", "gilt", "regelt", "nennt", "bei", "oder",
    "über", "gegen", "pflichten", "anbieter", "betreiber", "ich", "sie", "wir",
}  # fmt: skip
ENGLISH = {
    "the", "and", "is", "not", "which", "what", "how", "who", "for", "with", "a", "an", "of",
    "to", "in", "on", "does", "do", "are", "must", "there", "say", "says", "about", "against",
    "or", "by", "providers", "deployers", "i", "you", "we", "list", "explain",
}  # fmt: skip


def detect_language(text: str) -> str:
    """'de' or 'en', from function words and umlauts (the corpus has only these two)."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    german = sum(w in GERMAN for w in words) + 2 * len(re.findall(r"[äöüß]", text.lower()))
    english = sum(w in ENGLISH for w in words)
    return "de" if german > english else "en"
