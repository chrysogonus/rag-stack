# Build your own knowledge base

The engine in `src/rag_stack/` knows nothing about any subject. Everything about yours lives in a
**pack**, a folder under `packs/` that `RAG_PACK` selects. This guide takes you from a copy of the
sample pack to your own chatbot with its own evals. You can stop after step 4 and already have a
working chatbot that cites your documents.

[`packs/starter`](../packs/starter) is the code-free example, and
[`packs/cybersecurity`](../packs/cybersecurity) shows how far a pack can go. Set up the project
with the [README's quickstart](../README.md#quickstart) first.

## 1. Copy the starter

```bash
make new-pack NAME=recipes
```

The name must be lowercase letters, digits and underscores, because it also names a Python package
and an index. This creates `packs/recipes`, a copy of the starter pack without its eval results,
and it never overwrites an existing pack. Select it in `.env`:

```bash
RAG_PACK=recipes
```

Your pack gets its own index (`kb_recipes`) and data folder (`data/recipes`). If `.env` sets
`QDRANT_COLLECTION` or `DATA_DIR`, remove those lines, because they override every pack's own.

## 2. Say what it is about

- **`domain` in `pack.yaml`:** one phrase, such as `family recipes`. The question drafter uses it.
- **`prompts/system.md`:** the chatbot's instructions. Replace the description of the handbook and
  keep the rules. `{abstain}` stands for the exact refusal sentence, which the evals look for.
- **`prompts/baseline.md`:** the instructions for the general chatbot your pack is compared against.
- **`labels` in `pack.yaml`:** per language, `hint` (what a refusal suggests asking) and `ai` (the
  AI disclosure at the end of each answer). English and German have the other labels built in.
  Another language needs all six: `sources`, `retrieved`, `versions`, `indexed`, `hint` and `ai`.

## 3. Add your sources

Nothing outside the `sources` list in `pack.yaml` is ever ingested. Every source must state its
`id`, `name`, `license` (an SPDX identifier, or `LicenseRef-*` for other terms), `attribution` and
`url`, and they are shown with every answer that cites it. Make sure you are allowed to store and
quote each source, and record third-party ones in [`NOTICE.md`](../NOTICE.md).

Three types of source need no code:

| `parser` | What it reads | Main `config` |
|---|---|---|
| `files` | A folder in your pack: Markdown, text, HTML, PDF and Word. One unit per section (headings of levels 1-3), named `<path>#<heading>` | `path`, `include`, `url_template`, `language`, `version` |
| `web` | Pages from a list of URLs or a sitemap, respecting robots.txt and pacing each host | `urls`, `sitemap`, `include`, `max_pages`, `language`, `version` |
| `structured` | One unit per record of a CSV or JSON file. Fields naming other records become graph links | `path` or `url`, `records`, `fields`, `url_template`, `relations`, `language`, `version` |

Each type's options are documented at the top of its module in
[`ingestion/generic/`](../src/rag_stack/ingestion/generic). Replace `docs/` and `glossary.csv` with
your content, and point the `url` and `url_template` values at where your documents really live: the
copied ones point at this project's GitHub repository.

## 4. Ingest, index, ask

```bash
make services                           # Postgres and Qdrant
make ingest SOURCE=all                  # fetch, snapshot and chunk; unchanged sources are skipped
make index                              # embed into Qdrant and load the graph links
make ask Q="How long do I roast a chicken?"
make up                                 # the chat UI at http://localhost:5173
```

`make down` stops everything. `make up` leaves a running API as it is, so if the app is already
running, or after you edit `pack.yaml` or change `RAG_PACK`, run `make restart-api` so the API loads
the pack, and reload the page.

## 5. Dress the chat page

The optional `ui` section sets what the page shows. Anything you leave out gets a neutral default.

```yaml
ui:
  title: Recipe box
  heading: What are you cooking?
  placeholder: Ask about a recipe
  starters:
    - question: How long do I roast a chicken?
      source: mains            # this source's constellation lights up while the question is pointed at
  sources:                     # default: one constellation per source, named after it
    - {id: mains, label: Main courses, short: Mains}
    - {id: desserts, label: Desserts, short: Desserts, side: right}
  musings: [Preheating the oven, Tasting the sauce]   # the status line while an answer is written
```

Constellations are placed in the order you list them. Wide screens put the first half left of the
reading column unless a source names its `side`, and narrow screens fill rows of up to four.

YAML ends an unquoted value at `?` inside `{…}`, so write questions in block style, as above, or
quote them.

## 6. Recognize your IDs

If your domain has identifiers people ask about by name, such as a part number, a case number or
`RFC 9110`, add a `pack.py` next to `pack.yaml` with a `detect_ids` function. The IDs it returns
are looked up directly instead of being searched for, and the evals use them to count citations.

```python
import re


def detect_ids(text: str) -> list[str]:
    return [f"RFC {number}" for number in re.findall(r"\bRFC[ -]?(\d+)\b", text, re.IGNORECASE)]
```

It must return IDs in exactly the form of your units' `native_id`. A pack without `detect_ids`
finds no IDs and relies on search, which is fine for most document collections. `pack.py` can also
define `scoped`, as described in the next step, when building it takes code.

## 7. Teach it your vocabulary

These are optional. All the patterns in `retrieval` are case-insensitive regular expressions matched
against the question.

| In `pack.yaml` | What it does |
|---|---|
| `retrieval.related` | A question matching one of these asks about related items, so it also gets the graph neighbors of what it found |
| `retrieval.relation_filters` | Which link types such a question follows: `{when: 'cause', rels: [causes]}`. Without a match it follows all of them |
| `retrieval.asked_for` | `{source: regex}`: a source asked for by kind, whose units lead among the neighbors |
| `retrieval.scoped` | `{source: regex}`: a source named in the question, which is also searched on its own |
| `retrieval.citation_rels` | Link types whose far end a hit cites, kept even when search missed it |
| `languages` | The languages in your pack, first one winning ties, with `extra_words` that tell them apart in your domain. Each needs its `labels` |
| `fetch.hosts` | Per-host request intervals and credentials for `web` and Python sources. `fetch.user_agent` sets the user agent |

## 8. Measure it

A chatbot you can't measure is one you can't safely change. The eval set lives in
`packs/<name>/evals/`, and the copied questions are about the sample handbook, so replace them.

Each line of `golden.jsonl` is one question:

```json
{"id": "roast-chicken", "category": "paraphrase", "split": "test", "language": "en", "question": "How long do I roast a chicken?", "gold_ids": ["mains.md#roast-chicken"], "key_facts": ["About 80 minutes at 200 °C"], "needs_review": false}
```

- **`gold_ids`** are the units that hold the answer. An `abstention` question, which the chatbot
  should refuse, has none, and its key fact says it isn't answerable from the sources.
- **`split`:** tune settings on `dev`, and keep `test` as the holdout that decides pass or fail.
- **`category`** must be listed in `evals.categories` in `pack.yaml`. Scores are reported per category.
- **`follow_up_of`** names the previous question, for a question that depends on it.

Set up the judge first (`EVAL_JUDGE_*` in `.env`, ideally from another model family than the
chatbot), and optionally a baseline chatbot (`EVAL_BASELINE_*`). Then:

```bash
make eval-draft SOURCE=mains CATEGORY=paraphrase N=5   # draft questions into drafts.jsonl
make eval-retrieval                                    # retrieval only, free
make eval                                              # paid: asks and judges what changed, writes report.md
make evals                                             # checks the saved results against thresholds.yaml
```

Drafts never enter the set by themselves. Review each one, fix or drop it, set
`needs_review: false`, and move it into `golden.jsonl`. `thresholds.yaml` holds the minimum scores
on the `test` split: raise them deliberately, and never lower one to make a run pass.

## 9. Write a parser when you need one

For a format the generic sources can't read, name a module of your pack:
`parser: .parsers.notes`. It needs two functions. `fetch` gets the raw files, and `parse` must work
from those files alone, so that `make reparse` can rebuild the chunks offline. Whatever `parse`
needs from the config has to go into the snapshot.

```python
"""packs/recipes/parsers/notes.py: one unit per note of a JSON file."""

import hashlib
import json
from typing import Any

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.models import Chunk, Edge, Snapshot


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    # config is the source's `config`, plus its id, license, attribution, source_url and pack_root.
    body = fetcher.get(config["url"])  # robots.txt, pacing, retries and the cache come with it
    version = hashlib.sha256(body).hexdigest()[:12]
    stamp = json.dumps({"license": config["license"], "attribution": config["attribution"]})
    files = {"notes.json": body, "stamp.json": stamp.encode()}
    return Snapshot(config["id"], version, retrieved_at, files, {"notes.json": config["url"]})


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    notes = json.loads(snapshot.files["notes.json"])
    stamp = json.loads(snapshot.files["stamp.json"])
    chunks = [
        Chunk(
            source_id=snapshot.source_id,
            native_id=note["id"],  # the exact ID it is cited by
            title=note["title"],
            url=note["url"],
            source_version=snapshot.version,
            language="en",
            retrieved_at=snapshot.retrieved_at,
            text=note["text"],
            **stamp,
        )
        for note in notes
    ]
    edges = [
        Edge(src_id=note["id"], rel="related_to", dst_id=other, origin=snapshot.source_id)
        for note in notes
        for other in note.get("see_also", [])
    ]
    return chunks, edges
```

Give each parser a test in `packs/<name>/tests/unit/` with a small verbatim excerpt of the real
source in `tests/fixtures/`. `make test` runs them.

## 10. Check it against the contract

`make test` runs [`tests/contract/`](../tests/contract/test_pack_contract.py) on every pack. Treat
it as your checklist. It checks that:

- every source names its license, attribution and URL;
- every parser has `fetch` and `parse`;
- sources stored in the pack parse into units that carry their license;
- the prompts have no unfilled placeholders;
- the retrieval words and question kinds name your own sources and languages;
- the eval set uses your categories and languages, and sources stored in the pack contain its gold IDs;
- the chat page shows every source once, and its starters name your sources.

`make new-pack` also copied an end-to-end test to `tests/e2e/test_<name>_e2e.py`. It asks about the
sample content, so rewrite its questions for yours. `make e2e` runs it against a real LLM and a
throwaway collection.

## 11. Keep it fresh

```bash
make refresh    # ingest, check, build and score a new index; serve it only if it passes
make schedule   # run that weekly, for the pack active when you run this
make rollback   # serve the previous index again
```

Run `make schedule` again after changing `RAG_PACK`, because the timer keeps the pack it was
installed with.

## Learn from the cybersecurity pack

[`packs/cybersecurity`](../packs/cybersecurity) uses everything above on ten real sources:

- **`parsers/`:** one module per source or legal system, including paged APIs and XML catalogs;
- **`ids.py`:** ID detection across many families, such as `T1059.001`, `CVE-…` and `AI Act Art. 50(1)`;
- **`pack.py`:** builds `scoped` from the laws in `laws.py`, so a question naming a law also searches it;
- **`pack.yaml`:** relation filters, two languages, per-host credentials, and extra draft kinds;
- **`evals/`:** a golden set of 212 questions with its report and run history.
