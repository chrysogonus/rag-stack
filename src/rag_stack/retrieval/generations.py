"""Index generations: each refresh builds a collection `<alias>_<generation>`; the alias names
the one being served and `<alias>_previous` the one before it, for rollback."""

import re
from datetime import UTC, datetime
from typing import cast

from qdrant_client import QdrantClient, models

PREVIOUS = "_previous"


def collection_name(alias: str, generation: str) -> str:
    return f"{alias}_{generation}"


def generation_of(alias: str, collection: str) -> str:
    """The generation a collection holds; '' for the collection indexed before generations."""
    return "" if collection == alias else collection.removeprefix(f"{alias}_")


def new_generation() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")


def aliases(client: QdrantClient) -> dict[str, str]:
    return {a.alias_name: a.collection_name for a in client.get_aliases().aliases}


def serving(client: QdrantClient, alias: str) -> str | None:
    """The collection behind the alias, the pre-generation collection of that name, or None."""
    if target := aliases(client).get(alias):
        return target
    names = {c.name for c in client.get_collections().collections}
    return alias if alias in names else None


def previous(client: QdrantClient, alias: str) -> str | None:
    return aliases(client).get(alias + PREVIOUS)


def generations(client: QdrantClient, alias: str) -> list[str]:
    """Generation collections, oldest first."""
    pattern = re.compile(rf"{re.escape(alias)}_\d{{20}}")
    return sorted(c.name for c in client.get_collections().collections if pattern.fullmatch(c.name))


def copy_points(
    client: QdrantClient,
    source: str,
    target: str,
    selector: models.Filter | None = None,
    batch: int = 256,
) -> int:
    """Copy points with their vectors and payloads, so nothing is embedded again."""
    copied, offset = 0, None
    while True:
        records, offset = client.scroll(
            source, selector, limit=batch, offset=offset, with_payload=True, with_vectors=True
        )
        if records:
            client.upsert(
                target,
                [
                    # Scrolled vectors (dense lists, sparse vectors) are valid point vectors.
                    models.PointStruct(
                        id=r.id, vector=cast(models.VectorStruct, r.vector), payload=r.payload
                    )
                    for r in records
                ],
            )
            copied += len(records)
        if offset is None:
            return copied


def _point(client: QdrantClient, targets: dict[str, str]) -> None:
    """Point aliases at collections in one atomic change, replacing what they named."""
    current = aliases(client)
    client.update_collection_aliases(
        change_aliases_operations=[
            *(
                models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=name))
                for name in targets
                if name in current
            ),
            *(
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(collection_name=collection, alias_name=name)
                )
                for name, collection in targets.items()
            ),
        ]
    )


def promote(client: QdrantClient, alias: str, collection: str) -> None:
    """Serve `collection`; what was served becomes the previous generation."""
    targets = {alias: collection}
    if current := aliases(client).get(alias):
        targets[alias + PREVIOUS] = current
    _point(client, targets)


def rollback(client: QdrantClient, alias: str) -> tuple[str, str]:
    """Swap the served and the previous generation (a second rollback undoes the first).
    Returns (now served, now previous)."""
    current = aliases(client)
    if alias + PREVIOUS not in current:
        raise ValueError("no previous generation to roll back to")
    served, before = current[alias], current[alias + PREVIOUS]
    _point(client, {alias: before, alias + PREVIOUS: served})
    return before, served


def prune(client: QdrantClient, alias: str, keep: set[str]) -> list[str]:
    """Delete the generation collections not in `keep`; returns their names."""
    gone = [c for c in generations(client, alias) if c not in keep]
    for collection in gone:
        client.delete_collection(collection)
    return gone
