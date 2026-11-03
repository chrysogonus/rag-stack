from pathlib import Path

from rag_stack.pack import pack_file

# This pack's sources, for its parsers: names, licenses and attribution.
SOURCES = {s.id: s for s in pack_file(Path(__file__).parent).sources}

# Laws by source, for their parsers and for finding references to them in questions: the short
# name their unit IDs start with ("AI Act Art. 50(1)", "KI-MIG § 2"), then a regex of the names
# a question may use (case-insensitive).
EU_ACTS: dict[str, tuple[str, str]] = {
    "eu-ai-act": ("AI Act", r"AI Act|AI Regulation|KI-VO|KI-Verordnung|2024/1689"),
}
GERMAN_LAWS: dict[str, tuple[str, str]] = {
    "ki-mig": ("KI-MIG", r"KI-MIG|KI-Marktüberwachungs\w*"),
}


def eu_id(act: str, unit: str) -> str:
    """Native ID of a unit of an EU act: 'Art. 50(1)', 'Recital 133', 'Annex III 1(a)'."""
    # The AI Act's recitals and annexes keep their IDs from when it was the only act indexed.
    return unit if act == "AI Act" and not unit.startswith("Art.") else f"{act} {unit}"
