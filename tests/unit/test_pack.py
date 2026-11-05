import pytest
from pydantic import ValidationError

from rag_stack.agent.prompts import ABSTAIN
from rag_stack.config import Settings
from rag_stack.ingestion.pipeline import source_module
from rag_stack.pack import load_pack

MINI = """\
domain: the team's notes
sources:
  - id: notes
    name: Team notes
    license: CC0-1.0
    attribution: The team, CC0
    url: https://example.org/notes
    parser: some.module
    config: {path: notes}
prompts: {system: system.md, baseline: baseline.md}
labels:
  en: {hint: Name a note., ai: "*AI-generated.*"}
languages: {en: {}}
retrieval:
  related: ['relat', 'link']
  relation_filters: [{when: 'cause', rels: [causes]}]
  asked_for: {notes: '\\bnotes\\b'}
  scoped: {notes: 'team notes'}
  citation_rels: [cites]
evals:
  title: Notes golden set
  dataset: evals
  rubric: rubric.md
  categories: [id-exact, abstention]
"""


def write_pack(tmp_path, text: str = MINI, name: str = "mini") -> str:
    root = tmp_path / name
    root.mkdir(parents=True)
    (root / "pack.yaml").write_text(text)
    (root / "system.md").write_text("Answer from the sources. Otherwise: {abstain}\n")
    (root / "baseline.md").write_text("Answer. Otherwise: {abstain}\n")
    return str(tmp_path)


def test_a_pack_declares_its_sources_prompts_and_eval_set(tmp_path):
    pack = load_pack("mini", write_pack(tmp_path))

    assert pack.name == "mini"
    assert list(pack.sources) == ["notes"]
    assert pack.sources["notes"].config == {"path": "notes"}
    assert pack.system_prompt == f"Answer from the sources. Otherwise: {ABSTAIN}"
    assert pack.baseline_prompt == f"Answer. Otherwise: {ABSTAIN}"
    assert pack.evals.dataset == tmp_path / "mini/evals"
    assert pack.evals.rubric == tmp_path / "mini/rubric.md"


def test_a_typo_in_pack_yaml_fails_at_load(tmp_path):
    with pytest.raises(ValidationError, match="sourcse"):
        load_pack("mini", write_pack(tmp_path, MINI.replace("sources:", "sourcse:")))


def test_every_language_of_a_pack_needs_all_answer_labels(tmp_path):
    french = MINI.replace("languages: {en: {}}", "languages: {en: {}, fr: {}}").replace(
        '  en: {hint: Name a note., ai: "*AI-generated.*"}',
        '  en: {hint: Name a note., ai: "*AI-generated.*"}\n  fr: {hint: Nommez une note., ai: IA}',
    )
    # Core has English and German footer labels only: French must bring its own.
    with pytest.raises(ValueError, match="fr.*indexed.*retrieved.*sources.*versions"):
        load_pack("mini", write_pack(tmp_path, french))

    spelled_out = french.replace(
        "ai: IA}",
        "ai: IA, sources: Sources, retrieved: Sources trouvées, versions: Versions, "
        "indexed: La base couvre}",
    )
    pack = load_pack("mini", write_pack(tmp_path / "full", spelled_out))
    assert pack.labels["fr"]["indexed"] == "La base couvre"
    assert pack.labels["en"]["sources"] == "Sources"  # core's, completed by the pack's own


def test_a_parser_starting_with_a_dot_is_a_module_of_the_pack(tmp_path):
    packs = write_pack(tmp_path, MINI.replace("parser: some.module", "parser: .parsers.notes"))
    (tmp_path / "mini/parsers").mkdir()
    (tmp_path / "mini/parsers/notes.py").write_text("from ..helpers import NAME\n")
    (tmp_path / "mini/helpers.py").write_text("NAME = 'the notes parser'\n")

    source = load_pack("mini", packs).sources["notes"]

    assert source_module(source).NAME == "the notes parser"


def test_a_pack_without_code_finds_no_ids(tmp_path):
    assert load_pack("mini", write_pack(tmp_path)).detect_ids("What is LLM01?") == []


def test_the_retrieval_vocabulary_is_case_insensitive(tmp_path):
    words = load_pack("mini", write_pack(tmp_path)).vocabulary

    assert words.is_related("How do these LINK up?")
    assert not words.is_related("What is it?")
    assert words.relations("What does it cause?") == {"causes"}
    assert words.relations("How do they relate?") is None
    assert words.asked_sources("Which Notes say so?") == {"notes"}
    assert words.scoped_sources("In the Team Notes?") == {"notes"}
    assert words.citation_rels == {"cites"}


def test_a_question_is_in_the_pack_language_with_most_of_its_words_a_tie_going_to_the_first():
    from rag_stack.retrieval.language import detect_language

    both = {"en": [], "de": ["anbieter"]}
    assert detect_language("Welche Pflichten haben Anbieter?", both) == "de"
    assert detect_language("Anbieter", both) == "de"  # a pack's own word
    assert detect_language("Anbieter", {"en": [], "de": []}) == "en"  # tied at 0: the first
    assert detect_language("Wie ist das?", {"en": []}) == "en"  # one language: always it


def test_the_cybersecurity_pack_is_the_default():
    pack = Settings().pack

    assert pack.name == "cybersecurity"
    assert len(pack.sources) == 10
    assert pack.detect_ids("What is AML.T0051?") == ["AML.T0051"]


def test_a_pack_gets_its_own_index_and_data_directory(tmp_path):
    packs = write_pack(tmp_path)

    settings = Settings(rag_pack="mini", packs_dir=packs)

    # Another pack's refresh can't swap this one's index or overwrite its snapshots.
    assert (settings.qdrant_collection, settings.data_dir) == ("kb_mini", "data/mini")


def test_set_storage_settings_win_over_the_packs(tmp_path, monkeypatch):
    monkeypatch.setenv("QDRANT_COLLECTION", "kb_other")
    settings = Settings(rag_pack="mini", packs_dir=write_pack(tmp_path), data_dir="d")

    assert (settings.qdrant_collection, settings.data_dir) == ("kb_other", "d")


def test_the_cybersecurity_pack_keeps_the_index_and_data_it_always_had():
    settings = Settings()

    assert (settings.qdrant_collection, settings.data_dir) == ("kb_chunks", "data")


def test_a_parser_named_by_type_is_one_of_the_engines_generic_sources(tmp_path):
    from rag_stack.ingestion.generic import files

    packs = write_pack(tmp_path, MINI.replace("parser: some.module", "parser: files"))

    assert source_module(load_pack("mini", packs).sources["notes"]) is files
