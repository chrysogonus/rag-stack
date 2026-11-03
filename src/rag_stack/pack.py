"""A domain pack: what turns the engine into a knowledge base about one domain.

`packs/<name>/pack.yaml` declares the sources with their licenses, the prompts, the answer
labels, the languages, the retrieval vocabulary and the eval set. An optional `pack.py` next to
it adds code: `detect_ids(text)` for the domain's ID formats and `scoped` (source → regex) for
sources a question can name. `RAG_PACK` selects the pack; `Settings.pack` loads it."""

import importlib
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from rag_stack.agent.prompts import ABSTAIN
from rag_stack.retrieval.language import detect_language

PACKS = Path(__file__).parents[2] / "packs"
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
    """An allowlisted source: nothing else is ingested. `parser` is an importable module with
    `fetch(fetcher, config, retrieved_at) -> Snapshot` and `parse(snapshot) -> (chunks, edges)`."""

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


class Evals(Strict):
    title: str
    dataset: Path  # golden.jsonl, thresholds.yaml, results.json, report.md, history.jsonl
    rubric: Path
    categories: list[str]  # in report order; `abstention` cases expect a refusal


class PackFile(Strict):
    sources: list[Source]
    prompts: Prompts
    labels: dict[str, dict[str, str]]  # per language: `hint`, `ai` and any of LABELS's
    languages: dict[str, Language] = {"en": Language()}  # the first wins a tie
    retrieval: Retrieval = Retrieval()
    fetch: Fetch = Fetch()
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
    sources: dict[str, Source]
    system_prompt: str
    baseline_prompt: str
    labels: dict[str, dict[str, str]]
    languages: dict[str, list[str]]
    vocabulary: Vocabulary
    fetch: Fetch
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
    # A parser starting with a dot is one of the pack's modules: ".parsers.atlas".
    sources = {
        s.id: s.model_copy(update={"parser": package(root) + s.parser})
        if s.parser.startswith(".")
        else s
        for s in spec.sources
    }
    return Pack(
        name=name,
        root=root,
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
        evals=spec.evals.model_copy(
            update={"dataset": root / spec.evals.dataset, "rubric": root / spec.evals.rubric}
        ),
        detect_ids=getattr(hooks, "detect_ids", None) or (lambda text: []),
    )


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
