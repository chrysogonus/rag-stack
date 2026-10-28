from pathlib import Path
from types import SimpleNamespace

import pytest
from fakes.edges import FakeEdgeStore
from fakes.embeddings import FakeEmbedder, FakeReranker, FakeSparseEmbedder, chunk
from qdrant_client import QdrantClient

from rag_stack import refresh
from rag_stack.config import Settings
from rag_stack.evals import harness
from rag_stack.ingestion.models import Edge
from rag_stack.ingestion.pipeline import write_processed
from rag_stack.retrieval import generations as gens
from rag_stack.retrieval.index import embedding_in, ensure_collection, index_source

CASES = [
    {"question": "What is AML.T0001?", "split": "dev", "category": "id-exact",
     "gold_ids": ["AML.T0001"]},
    {"question": "What is LLM01:2026?", "split": "test", "category": "id-exact",
     "gold_ids": ["LLM01:2026"]},
]  # fmt: skip
EDGE = Edge(src_id="AML.T0001", rel="mitigated_by", dst_id="AML.M0001", origin="atlas")


class CountingEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.embedded = 0

    def embed_documents(self, texts):
        self.embedded += len(texts)
        return super().embed_documents(texts)


def atlas(n: int = 10, text: str = "text") -> list:
    return [chunk(f"AML.T{i:04d}", f"{text} {i}") for i in range(1, n + 1)]


def owasp() -> list:
    return [chunk("LLM01:2026", "Prompt injection", source_id="owasp-llm-2026")]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A data dir with two processed sources, in-memory Qdrant and edge store, two questions."""
    monkeypatch.setattr(harness, "load_cases", lambda: CASES)
    settings = Settings(data_dir=str(tmp_path), qdrant_collection="kb", database_url="fake")
    store = FakeEdgeStore().install(monkeypatch)
    embedder = CountingEmbedder()
    embedder.name = settings.embedding  # the configured model, as a real index would hold

    def write(source_id: str, sha: str, chunks: list, edges=()) -> None:
        root = tmp_path / "processed" / source_id
        write_processed(root / sha, chunks, list(edges), sha)
        (root / "LATEST").write_text(sha)

    def models():
        return embedder, FakeSparseEmbedder(), FakeReranker()

    def run(failed=(), force=False):
        return refresh.refresh(settings, client, list(failed), models, force)

    client = QdrantClient(":memory:")
    write("atlas", "a1", atlas(), [EDGE])
    write("owasp-llm-2026", "o1", owasp())
    # Indexed before generations existed: a real collection named like the alias.
    ensure_collection(client, "kb", embedder.dim)
    index_source(client, "kb", "atlas", "a1", atlas(), embedder, FakeSparseEmbedder())
    index_source(client, "kb", "owasp-llm-2026", "o1", owasp(), embedder, FakeSparseEmbedder())
    store.rows[""] = [EDGE]
    embedder.embedded = 0

    return SimpleNamespace(
        settings=settings, client=client, store=store, embedder=embedder, write=write, run=run
    )


def lines(env) -> list[str]:
    return (Path(env.settings.data_dir) / "refresh.log").read_text().splitlines()


def test_diff_counts_native_ids_once_however_many_parts():
    before = [chunk("A", "one"), chunk("A", "two", chunk_index=1), chunk("B")]
    after = [chunk("A", "one, changed"), chunk("C")]
    d = refresh.diff(before, after)
    assert (d.added, d.removed, d.changed) == (1, 1, 1)
    assert (d.chunks, d.ids) == ((3, 2), (2, 2))


def test_gate_blocks_a_source_that_shrank_by_more_than_ten_percent():
    def shrink(old: int, new: int) -> refresh.Diff:
        return refresh.Diff(0, 0, 0, (old, new), (old, new))

    assert refresh.gate({"atlas": shrink(100, 91)}) == []
    assert refresh.gate({"atlas": shrink(100, 89)}) == [
        "atlas chunks 100→89 (-11%)",
        "atlas IDs 100→89 (-11%)",
    ]
    assert refresh.gate({"new": shrink(0, 5)}) == []


def test_promote_keeps_the_previous_generation_and_rollback_swaps_them():
    client = QdrantClient(":memory:")
    for g in ("20260101000000000000", "20260102000000000000", "20260103000000000000"):
        ensure_collection(client, f"kb_{g}", 4)
    gens.promote(client, "kb", "kb_20260101000000000000")
    gens.promote(client, "kb", "kb_20260102000000000000")
    assert gens.aliases(client) == {
        "kb": "kb_20260102000000000000",
        "kb_previous": "kb_20260101000000000000",
    }

    assert gens.rollback(client, "kb") == ("kb_20260101000000000000", "kb_20260102000000000000")
    gens.rollback(client, "kb")
    assert gens.aliases(client) == {
        "kb": "kb_20260102000000000000",
        "kb_previous": "kb_20260101000000000000",
    }

    assert gens.prune(client, "kb", {"kb_20260102000000000000", "kb_20260101000000000000"}) == [
        "kb_20260103000000000000"
    ]
    assert gens.generation_of("kb", "kb_20260102000000000000") == "20260102000000000000"
    assert gens.generation_of("kb", "kb") == ""


@pytest.mark.anyio
async def test_the_first_refresh_adopts_the_old_collection_without_embedding_anything(env):
    def no_models():
        raise AssertionError("models are loaded only to build a candidate")

    code, line = await refresh.refresh(env.settings, env.client, [], no_models)

    assert code == 0 and " NO CHANGE | adopted kb as kb_" in line
    served = gens.serving(env.client, "kb")
    assert served and served.startswith("kb_") and env.client.count(served).count == 11
    assert list(env.store.rows) == [gens.generation_of("kb", served)]
    assert env.store.rows[gens.generation_of("kb", served)] == [EDGE]

    code, line = await refresh.refresh(env.settings, env.client, [], no_models)
    assert line.endswith(" - NO CHANGE") and gens.serving(env.client, "kb") == served
    assert lines(env)[-1] == line


@pytest.mark.anyio
async def test_a_changed_source_is_embedded_and_the_rest_copied_then_promoted(env):
    await env.run()
    served = gens.serving(env.client, "kb")
    env.write("atlas", "a2", atlas(11, "new text"), [EDGE])

    code, line = await env.run(failed=["ki-mig"])

    assert code == 0, line
    assert " PROMOTED | atlas 2026.09: +1 -0 ~10 IDs, 10→11 chunks; 1 sources unchanged" in line
    assert "ingest failed: ki-mig (previous snapshot kept)" in line
    assert "recall_at_10 1.000 (served 1.000)" in line
    assert env.embedder.embedded == 11  # the atlas chunks; owasp was copied with its vectors
    candidate = gens.serving(env.client, "kb")
    assert served and candidate and candidate != served
    assert gens.previous(env.client, "kb") == served
    assert env.client.count(candidate).count == 12
    assert set(env.store.rows) == {gens.generation_of("kb", c) for c in (served, candidate)}

    assert refresh.rollback(env.settings, env.client)[0] == 0
    assert gens.serving(env.client, "kb") == served


@pytest.mark.anyio
async def test_only_new_and_changed_chunks_of_a_changed_source_are_embedded(env):
    await env.run()
    changed = [*atlas(9), chunk("AML.T0010", "revised 10"), chunk("AML.T0011", "text 11")]
    env.write("atlas", "a2", changed, [EDGE])

    code, line = await env.run()

    assert code == 0 and " PROMOTED " in line, line
    assert env.embedder.embedded == 2

    # A new source version alone embeds nothing, but the payload carries the new version.
    bumped = [c.model_copy(update={"source_version": "2026.10"}) for c in changed]
    env.write("atlas", "a3", bumped, [EDGE])
    code, line = await env.run()
    assert code == 0 and env.embedder.embedded == 2, line
    served = gens.serving(env.client, "kb")
    assert served
    point = env.client.retrieve(served, [bumped[0].point_id], with_payload=True)[0]
    assert point.payload and point.payload["source_version"] == "2026.10"


@pytest.mark.anyio
async def test_a_source_that_shrank_blocks_before_anything_is_built(env):
    await env.run()
    env.write("atlas", "a2", atlas(5))

    code, line = await env.run()

    assert code == 1 and "BLOCKED: atlas chunks 10→5 (-50%); atlas IDs 10→5 (-50%)" in line
    assert env.embedder.embedded == 0 and len(gens.generations(env.client, "kb")) == 1

    code, line = await env.run(force=True)
    assert code == 0 and " PROMOTED " in line


@pytest.mark.anyio
async def test_a_retired_source_is_dropped_and_one_without_a_snapshot_blocks(env, monkeypatch):
    await env.run()
    served = gens.serving(env.client, "kb")
    monkeypatch.setattr(harness, "load_cases", lambda: CASES[:1])
    monkeypatch.setattr(refresh, "MODULES", {"atlas": "atlas"})

    code, line = await env.run()

    assert code == 0 and " PROMOTED " in line and "removed: owasp-llm-2026" in line, line
    candidate = gens.serving(env.client, "kb")
    assert candidate != served and env.client.count(candidate).count == 10

    # A source still in MODULES whose snapshot is gone is not retired: it blocks.
    monkeypatch.setattr(refresh, "MODULES", {"atlas": "atlas", "ki-mig": "gesetze_im_internet"})
    env.client.upsert(
        candidate, env.client.retrieve(served, [owasp()[0].point_id], with_vectors=True)
    )
    env.client.set_payload(candidate, {"source_id": "ki-mig"}, [owasp()[0].point_id])
    code, line = await env.run()
    assert code == 1 and "BLOCKED: ki-mig has no processed snapshot" in line, line


@pytest.mark.anyio
async def test_a_missing_gold_id_blocks_even_when_forced(env):
    await env.run()
    env.write("atlas", "a2", atlas()[1:])

    code, line = await env.run(force=True)

    assert code == 1 and "gold IDs missing: AML.T0001" in line


@pytest.mark.anyio
async def test_a_retrieval_regression_blocks_and_keeps_the_candidate_for_inspection(
    env, monkeypatch
):
    await env.run()
    served = gens.serving(env.client, "kb")
    env.write("atlas", "a2", atlas(10, "changed"))
    real = harness.retrieval_scores

    async def worse_candidate(kb, split):
        summary, seconds = await real(kb, split)
        if kb.collection != served:
            summary["all"] = {"recall_at_10": 0.95, "mrr": 0.9}
        return summary, seconds

    monkeypatch.setattr(harness, "retrieval_scores", worse_candidate)

    code, line = await env.run()

    assert code == 1 and "BLOCKED: recall_at_10 0.950 < served 1.000 - 0.02" in line
    assert gens.serving(env.client, "kb") == served
    assert len(gens.generations(env.client, "kb")) == 2
    # The next run prunes the blocked candidate.
    monkeypatch.setattr(harness, "retrieval_scores", real)
    env.write("atlas", "a1", atlas(), [EDGE])
    await env.run()
    assert gens.generations(env.client, "kb") == [served]


def test_rollback_without_a_previous_generation_fails(env):
    code, line = refresh.rollback(env.settings, env.client)
    assert code == 1 and "ROLLBACK FAILED: no previous generation" in line


def test_only_one_refresh_runs_at_a_time(env):
    with refresh.locked(env.settings), pytest.raises(BlockingIOError):
        with refresh.locked(env.settings):
            pass


@pytest.mark.anyio
async def test_a_blocked_first_build_is_never_served_by_a_later_run(env, monkeypatch):
    env.client.delete_collection("kb")  # a fresh machine: nothing indexed yet
    real = harness.retrieval_scores

    async def nothing_found(kb, split):
        return {"all": {"recall_at_10": 0.0, "mrr": 0.0}}, []

    monkeypatch.setattr(harness, "retrieval_scores", nothing_found)
    assert (await env.run())[0] == 1
    assert (await env.run())[0] == 1
    assert gens.serving(env.client, "kb") is None

    monkeypatch.setattr(harness, "retrieval_scores", real)
    code, line = await env.run()
    assert code == 0 and " PROMOTED " in line


@pytest.mark.anyio
async def test_a_failed_cleanup_still_reports_the_promotion(env, monkeypatch):
    await env.run()
    env.write("atlas", "a2", atlas(11))

    def broken(*args):
        raise OSError("Postgres went away")

    monkeypatch.setattr(refresh, "tidy", broken)
    code, line = await env.run()

    assert code == 0 and " PROMOTED " in line and "cleanup failed: Postgres went away" in line


@pytest.mark.anyio
async def test_a_new_embedding_model_rebuilds_everything_and_scores_the_served_index_as_it_ran(
    env,
):
    await env.run()
    served = gens.serving(env.client, "kb")
    settings = env.settings.model_copy(update={"embedding_model": "intfloat/other"})
    new = CountingEmbedder()
    new.name = settings.embedding
    loaded: list[str] = []

    def load_embedder(name: str):
        loaded.append(name)
        return env.embedder

    code, line = await refresh.refresh(
        settings,
        env.client,
        [],
        lambda: (new, FakeSparseEmbedder(), FakeReranker()),
        load_embedder=load_embedder,
    )

    assert code == 0 and " PROMOTED " in line, line
    assert f"embedding {env.settings.embedding} → {settings.embedding}: rebuilt in full" in line
    assert new.embedded == 11 and env.embedder.embedded == 0  # nothing copied or reused
    assert loaded == [env.settings.embedding] and "(served 1.000)" in line
    candidate = gens.serving(env.client, "kb")
    assert candidate and candidate != served
    assert embedding_in(env.client, candidate) == settings.embedding

    # Same model again: nothing to do.
    def no_models():
        raise AssertionError("nothing to build")

    code, line = await refresh.refresh(settings, env.client, [], no_models)
    assert line.endswith(" - NO CHANGE"), line


def test_vectors_of_another_model_are_never_reused():
    client = QdrantClient(":memory:")
    old, new = CountingEmbedder(), CountingEmbedder()
    new.name = "fastembed:other"
    for collection in ("served", "candidate"):
        ensure_collection(client, collection, old.dim)
    index_source(client, "served", "atlas", "a1", atlas(3), old, FakeSparseEmbedder())

    index_source(
        client, "candidate", "atlas", "a1", atlas(3), new, FakeSparseEmbedder(), reuse_from="served"
    )

    assert new.embedded == 3
    assert embedding_in(client, "candidate") == "fastembed:other"
    assert embedding_in(client, "served") == old.name
