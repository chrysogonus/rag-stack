"""A domain pack: what turns the engine into a knowledge base about one domain.

`packs/<name>/pack.yaml` declares the sources with their licenses, the prompts, the answer
labels, the languages, the retrieval vocabulary, the chat page and the eval set. An optional
`pack.py` next to it adds code: `detect_ids(text)` for the domain's ID formats and `scoped`
(source → regex) for sources a question can name. `RAG_PACK` selects the pack; `Settings.pack`
loads it."""

import importlib
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rag_stack.agent.prompts import ABSTAIN
from rag_stack.retrieval.language import detect_language

PACKS = Path(__file__).parents[2] / "packs"
GENERIC = "rag_stack.ingestion.generic."
# The answer footer's and the refusal's labels. A pack adds `hint` (what a refusal suggests
# asking) and `ai` (the AI disclosure), and brings all six for a language other than these.
LABELS = {
    "en": {
        "sources": "Sources",
        "retrieved": "Retrieved sources (none cited)",
        "versions": "Source versions",
        "indexed": "The knowledge base covers",
    },
    "de": {
        "sources": "Quellen",
        "retrieved": "Abgerufene Quellen (keine zitiert)",
        "versions": "Quellenversionen",
        "indexed": "Die Wissensbasis umfasst",
    },
}
LABEL_NAMES = {"sources", "retrieved", "versions", "indexed", "hint", "ai"}


class Strict(BaseModel):
    # A typo in pack.yaml fails at load instead of being ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Strict):
    """An allowlisted source: nothing else is ingested. `parser` is one of the engine's generic
    sources by type (`files`, `web`, `structured`, configured by `config`), a module of the pack
    (`.parsers.atlas`) or any importable module, with `fetch(fetcher, config, retrieved_at) ->
    Snapshot` and `parse(snapshot) -> (chunks, edges)`."""

    id: str
    name: str
    license: str  # SPDX where one exists, LicenseRef-* otherwise (see NOTICE.md)
    attribution: str
    url: str
    parser: str
    config: dict[str, Any] = {}


class Prompts(Strict):
    # Files relative to the pack; `{abstain}` stands for the refusal sentence evals key on.
    system: Path
    baseline: Path


class Language(Strict):
    # Words of the domain that tell its questions' language apart, beyond common function words.
    extra_words: list[str] = []


class RelationFilter(Strict):
    when: str
    rels: list[str]


class Retrieval(Strict):
    """Regexes, all case-insensitive, over the question."""

    # A question about related items: it gets the graph neighbors of the units it is about.
    related: list[str] = []
    # Which relations such a question follows: the first match's, otherwise all.
    relation_filters: list[RelationFilter] = []
    # A source asked for by kind ("Which CAPEC patterns ..."): its units lead among neighbors.
    asked_for: dict[str, str] = {}
    # A source named in the question ("under the KI-MIG"): also searched on its own.
    scoped: dict[str, str] = {}
    # Relations whose far end a hit cites: kept even when search missed it.
    citation_rels: list[str] = []


class Credential(Strict):
    """A key or token a host serves more requests with, sent as a header when it is set."""

    env: str  # the environment variable, or `.env` entry, holding it
    header: str
    value: str = "{}"  # the header's value; {} stands for the credential
    interval: float  # seconds between requests with it


class Host(Strict):
    interval: float  # seconds between requests (robots.txt may ask for more)
    credential: Credential | None = None


class Fetch(Strict):
    user_agent: str = "rag-stack/0.1 (knowledge base ingest)"
    hosts: dict[str, Host] = {}  # other hosts get one request per second


class Storage(Strict):
    collection: str | None = None  # the Qdrant alias it is served under; default kb_<pack>
    data_dir: str | None = None  # snapshots and caches; default data/<pack>


class DraftKind(Strict):
    """A kind of question `make eval-draft` writes, beyond id-exact, paraphrase, cross-source."""

    ask: str  # what the question does: "asks about the vulnerability by its CVE id"
    language: str | None = None  # it is in this language (default: the source's main one)
    sources: list[str] | None = None  # only these sources' units fit it (default: all)


# What each kind of drafted question does; the drafter sees this and the unit's text.
DRAFT_KINDS = {
    "id-exact": DraftKind(ask="names the unit's id and asks what it is or says"),
    "paraphrase": DraftKind(
        ask="asks about the unit's content in a user's own words, without naming its id"
    ),
    "cross-source": DraftKind(
        ask="asks how the two units relate, naming one of them, so answering needs both"
    ),
}


class Evals(Strict):
    title: str
    dataset: Path  # golden.jsonl, thresholds.yaml, results.json, report.md, history.jsonl
    rubric: Path
    categories: list[str]  # in report order; `abstention` cases expect a refusal
    draft_kinds: dict[str, DraftKind] = {}  # the pack's own; loaded, DRAFT_KINDS's too


class UiSource(Strict):
    id: str
    label: str
    short: str  # for narrow screens, where up to four constellations share a row
    side: Literal["left", "right"] | None = None  # of the reading column, on wide screens


class Starter(Strict):
    question: str
    source: str  # its constellation lights up while the question is pointed at


class Ui(Strict):
    """What the chat page shows; neutral unless the pack says otherwise."""

    title: str = "Knowledge base"
    heading: str = "What do you want to know?"
    intro: str = (
        "Each constellation is one source. When you ask, the passages behind the answer light up. "
        "Answers come from an AI model and can be wrong, so check anything important."
    )
    placeholder: str = "Ask a question"
    # One constellation each, default one per source. Order places them: wide screens put the
    # first half left of the reading column unless a source names its `side`, narrow ones fill
    # rows of four, then three.
    sources: list[UiSource] = []
    starters: list[Starter] = []
    # The status line while an answer is written.
    musings: Annotated[list[str], Field(min_length=1)] = [
        "Turning the pages",
        "Checking the footnotes",
        "Following the references",
        "Comparing the passages",
        "Reading the fine print",
        "Asking the librarian",
    ]


class PackFile(Strict):
    domain: str  # what the knowledge base is about, in a phrase: "the team's handbook"
    sources: list[Source]
    prompts: Prompts
    labels: dict[str, dict[str, str]]  # per language: `hint`, `ai` and any of LABELS's
    languages: dict[str, Language] = {"en": Language()}  # the first wins a tie
    retrieval: Retrieval = Retrieval()
    fetch: Fetch = Fetch()
    storage: Storage = Storage()
    ui: Ui = Ui()
    evals: Evals


@dataclass(frozen=True)
class Vocabulary:
    """A pack's retrieval vocabulary, compiled."""

    related: re.Pattern[str] | None
    relation_filters: list[tuple[re.Pattern[str], set[str]]]
    asked_for: dict[str, re.Pattern[str]]
    scoped: dict[str, re.Pattern[str]]
    citation_rels: frozenset[str]

    def is_related(self, query: str) -> bool:
        return bool(self.related and self.related.search(query))

    def relations(self, query: str) -> set[str] | None:
        """The relations a question about related items follows (None: all)."""
        found = (rels for pattern, rels in self.relation_filters if pattern.search(query))
        return next(found, None)

    def asked_sources(self, query: str) -> set[str]:
        return {source for source, pattern in self.asked_for.items() if pattern.search(query)}

    def scoped_sources(self, query: str) -> set[str]:
        return {source for source, pattern in self.scoped.items() if pattern.search(query)}


@dataclass(frozen=True)
class Pack:
    name: str
    root: Path
    domain: str
    sources: dict[str, Source]
    system_prompt: str
    baseline_prompt: str
    labels: dict[str, dict[str, str]]
    languages: dict[str, list[str]]
    vocabulary: Vocabulary
    fetch: Fetch
    collection: str
    data_dir: str
    ui: Ui
    evals: Evals
    detect_ids: Callable[[str], list[str]]

    def detect_language(self, text: str) -> str:
        return detect_language(text, self.languages)


@cache
def pack_file(root: Path) -> PackFile:
    """pack.yaml alone, without the pack's code."""
    return PackFile.model_validate(yaml.safe_load((root / "pack.yaml").read_text()))


@cache
def load_pack(name: str, packs_dir: str) -> Pack:
    root = Path(packs_dir) / name
    spec = pack_file(root)
    hooks = pack_code(root)

    def prompt(path: Path) -> str:
        return (root / path).read_text().rstrip("\n").replace("{abstain}", ABSTAIN)

    def compiled(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern, re.I)

    given = spec.labels
    labels = {code: {**LABELS.get(code, {}), **given.get(code, {})} for code in spec.languages}
    for code, named in labels.items():
        if missing := sorted(LABEL_NAMES - named.keys()):
            raise ValueError(f"pack {name}: labels for {code} miss {', '.join(missing)}")
    words = spec.retrieval
    sources = {s.id: s.model_copy(update={"parser": parser(root, s.parser)}) for s in spec.sources}
    return Pack(
        name=name,
        root=root,
        domain=spec.domain,
        sources=sources,
        system_prompt=prompt(spec.prompts.system),
        baseline_prompt=prompt(spec.prompts.baseline),
        labels=labels,
        languages={code: lang.extra_words for code, lang in spec.languages.items()},
        vocabulary=Vocabulary(
            related=compiled("|".join(words.related)) if words.related else None,
            relation_filters=[(compiled(f.when), set(f.rels)) for f in words.relation_filters],
            asked_for={s: compiled(p) for s, p in words.asked_for.items()},
            scoped={
                s: compiled(p) for s, p in {**words.scoped, **getattr(hooks, "scoped", {})}.items()
            },
            citation_rels=frozenset(words.citation_rels),
        ),
        fetch=spec.fetch,
        collection=spec.storage.collection or f"kb_{name}",
        data_dir=spec.storage.data_dir or f"data/{name}",
        ui=spec.ui.model_copy(
            update={
                "sources": spec.ui.sources
                or [UiSource(id=s.id, label=s.name, short=s.name) for s in spec.sources]
            }
        ),
        evals=spec.evals.model_copy(
            update={
                "dataset": root / spec.evals.dataset,
                "rubric": root / spec.evals.rubric,
                "draft_kinds": {**DRAFT_KINDS, **spec.evals.draft_kinds},
            }
        ),
        detect_ids=getattr(hooks, "detect_ids", None) or (lambda text: []),
    )


def new_pack(name: str, packs_dir: str) -> Path:
    """Copy the starter pack to `<packs_dir>/<name>` under that name, without its eval results.
    The name also names a Python package and an index, so it can't leave the packs directory."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError(f"pack name {name!r}: use lowercase letters, digits and underscores")
    root = Path(packs_dir) / name
    generated = ("results.json", "report.md", "history.jsonl", "corpus", "__pycache__")
    shutil.copytree(PACKS / "starter", root, ignore=shutil.ignore_patterns(*generated))
    manifest = root / "pack.yaml"
    manifest.write_text(re.sub(r"\bstarter\b", name, manifest.read_text()))
    # pytest needs test file names unique across packs: a pack named chat can't have test_chat.py.
    test = (root / "tests/e2e/test_starter.py").rename(root / f"tests/e2e/test_{name}_e2e.py")
    test.write_text(test.read_text().replace('rag_pack="starter"', f'rag_pack="{name}"'))
    return root


def parser(root: Path, name: str) -> str:
    """The module a source's `parser` names: a generic source by its type ("files"), one of the
    pack's modules when it starts with a dot (".parsers.atlas"), or the module itself."""
    if name.startswith("."):
        return package(root) + name
    return name if "." in name else GENERIC + name


def package(root: Path) -> str:
    """The pack's modules' package, `<packs dir>.<name>`, so they can import each other."""
    parent = str(root.parent.parent)
    if parent not in sys.path:
        sys.path.append(parent)
    return f"{root.parent.name}.{root.name}"


def pack_code(root: Path) -> ModuleType | None:
    """The pack's pack.py."""
    path = root / "pack.py"
    if not path.exists():
        return None
    module = importlib.import_module(f"{package(root)}.pack")
    if Path(str(module.__file__)).resolve() != path.resolve():
        raise ImportError(f"{module.__name__} is {module.__file__}, not {path}")
    return module
