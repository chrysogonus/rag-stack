"""What every pack in packs/ must keep, whoever wrote it: a checklist for a new pack.

`make test` runs it for each pack; a pack's own parsers are tested by its own tests."""

import json
import re
from pathlib import Path

import httpx
import pytest
import yaml

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk
from rag_stack.ingestion.pipeline import source_config, source_module
from rag_stack.pack import GENERIC, PACKS, Pack, load_pack

NAMES = sorted(p.parent.name for p in PACKS.glob("*/pack.yaml"))
# SPDX identifiers, or LicenseRef-* for terms SPDX doesn't list (see NOTICE.md).
LICENSE = re.compile(r"^(LicenseRef-[\w.-]+|[A-Za-z0-9][\w.+-]*)$")
LOCAL = {f"{GENERIC}files", f"{GENERIC}structured"}


@pytest.fixture(params=NAMES)
def pack(request) -> Pack:
    return load_pack(request.param, str(PACKS))


def local_units(pack: Pack) -> dict[str, list[Chunk]]:
    """The units of the pack's sources that live in the pack (a folder, a local file)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"a local source fetched {request.url}")

    fetcher = Fetcher("contract", Path("/nonexistent"), 0, transport=httpx.MockTransport(handler))
    units = {}
    for source in pack.sources.values():
        if source.parser in LOCAL and "url" not in source.config:
            module = source_module(source)
            snapshot = module.fetch(fetcher, source_config(source, pack), "2026-01-01T00:00:00")
            units[source.id] = module.parse(snapshot)[0]
    return units


def test_every_source_names_its_license_attribution_and_home(pack):
    for source in pack.sources.values():
        assert LICENSE.match(source.license), f"{source.id}: {source.license!r} isn't SPDX"
        assert source.attribution.strip(), f"{source.id}: no attribution"
        assert source.url.startswith("https://"), f"{source.id}: {source.url}"


def test_every_parser_fetches_and_parses(pack):
    for source in pack.sources.values():
        module = source_module(source)
        assert callable(module.fetch) and callable(module.parse), source.parser


def test_sources_in_the_pack_parse_into_units_that_carry_their_license(pack):
    for source_id, chunks in local_units(pack).items():
        source = pack.sources[source_id]
        assert chunks, f"{source_id}: no units"
        assert {(c.license, c.attribution) for c in chunks} == {
            (source.license, source.attribution)
        }
        keys = [(c.native_id, c.language) for c in chunks]
        assert len(keys) == len(set(keys)), f"{source_id}: unit IDs repeat"


def test_the_prompts_have_no_unfilled_placeholders(pack):
    for prompt in (pack.system_prompt, pack.baseline_prompt):
        assert not re.search(r"\{[a-z_]+\}", prompt), prompt


def test_the_retrieval_words_and_question_kinds_name_the_packs_sources_and_languages(pack):
    words = pack.vocabulary
    assert set(words.asked_for) | set(words.scoped) <= set(pack.sources)
    for kind in pack.evals.draft_kinds.values():
        assert set(kind.sources or []) <= set(pack.sources)
        assert kind.language in {None, *pack.languages}


def test_the_eval_set_asks_in_the_packs_categories_and_languages(pack):
    dataset = pack.evals.dataset
    assert pack.evals.rubric.read_text().strip()
    assert yaml.safe_load((dataset / "thresholds.yaml").read_text())
    cases = [json.loads(line) for line in (dataset / "golden.jsonl").read_text().splitlines()]
    assert cases
    for case in cases:
        assert case["category"] in pack.evals.categories, case["id"]
        assert case["language"] in pack.languages, case["id"]
        assert case["split"] in {"dev", "test"}, case["id"]
        assert case["key_facts"], case["id"]
        assert bool(case["gold_ids"]) != (case["category"] == "abstention"), case["id"]
    assert len({c["id"] for c in cases}) == len(cases)


def test_gold_ids_are_units_of_the_pack_when_all_its_sources_live_in_it(pack):
    units = local_units(pack)
    if set(units) != set(pack.sources):
        pytest.skip("units of fetched sources are checked by `make eval-units`")
    known = {i for chunks in units.values() for c in chunks for i in (c.native_id, *c.parent_ids)}
    cases = [json.loads(line) for line in (pack.evals.dataset / "golden.jsonl").open()]
    for case in cases:
        assert set(case["gold_ids"]) <= known, (case["id"], set(case["gold_ids"]) - known)


def test_the_ui_shows_every_source_once_and_its_starters_name_them(pack):
    shown = [s.id for s in pack.ui.sources]
    assert sorted(shown) == sorted(pack.sources)
    assert {s.source for s in pack.ui.starters} <= set(pack.sources)
