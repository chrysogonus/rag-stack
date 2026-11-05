"""Records of a CSV or JSON file (`parser: structured`): one unit per record.

config:
  path: glossary.csv          # in the pack, or `url:` to download it; .csv, otherwise JSON
  records: data.items         # JSON: the dotted path to the list of records (default: the top)
  fields:
    id: term                  # the unit's ID
    title: term               # (default: the ID)
    text: [definition, note]  # one field, or several labeled "field: value"
  url_template: https://example.org/glossary#{term}   # (default: the source's url)
  relations:                  # fields naming other units' IDs, as edges
    - {field: see_also, rel: related_to, split: ";"}
  language: en                # (default en)
  version: "2026.1"           # (default: the content's digest)"""

import csv
import io
import json
from pathlib import Path, PurePosixPath
from typing import Any

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.generic.chunking import snapshot, unstamped
from rag_stack.ingestion.models import Chunk, Edge, Snapshot


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    if url := config.get("url"):
        name = PurePosixPath(url.split("?")[0]).name or "records.json"
        return snapshot(config, retrieved_at, {name: fetcher.get(url)}, {name: url})
    path = Path(config["pack_root"]) / config["path"]
    return snapshot(config, retrieved_at, {path.name: path.read_bytes()}, {})


def records(name: str, content: bytes, path: str | None) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    if name.lower().endswith(".csv"):
        return list(csv.DictReader(io.StringIO(text)))
    found = json.loads(text)
    for key in path.split(".") if path else []:
        found = found[key]
    if not isinstance(found, list):
        raise ValueError(f"{name}: the records at {path or 'the top'} are not a list")
    return found


def values(value: Any, split: str | None) -> list[str]:
    """A relation field's IDs: a list, or a string split at `split`."""
    items = value if isinstance(value, list) else str(value).split(split) if split else [value]
    return [s for item in items if item is not None and (s := str(item).strip())]


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    config, files, common = unstamped(snapshot)
    ((name, content),) = files.items()
    fields = config["fields"]
    texts = [fields["text"]] if isinstance(fields["text"], str) else fields["text"]
    template = config.get("url_template")
    chunks, edges = [], []
    for n, record in enumerate(records(name, content, config.get("records")), start=1):
        value = record.get(fields["id"])  # 0 is an ID; None and blanks are not
        if value is None or not (native_id := str(value).strip()):
            raise ValueError(f"{name}: record {n} has no {fields['id']}")
        present = [(f, str(record[f]).strip()) for f in texts if record.get(f) not in (None, "")]
        text = (
            present[0][1]
            if len(texts) == 1 and present
            else "\n\n".join(f"{f}: {v}" for f, v in present)
        )
        chunks.append(
            Chunk(
                native_id=native_id,
                title=str(record.get(fields.get("title", fields["id"])) or native_id),
                url=template.format(**record) if template else config["source_url"],
                text=text,
                **common,
            )
        )
        for relation in config.get("relations", []):
            edges += [
                Edge(src_id=native_id, rel=relation["rel"], dst_id=dst, origin=snapshot.source_id)
                for dst in values(record.get(relation["field"], ""), relation.get("split"))
            ]
    return chunks, edges
