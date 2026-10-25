from pathlib import Path

import httpx
import pytest
from fakes.embeddings import chunk

from rag_stack.config import Settings
from rag_stack.ingestion import pipeline
from rag_stack.ingestion.fetch import Fetcher, FetchError
from rag_stack.ingestion.models import finalize, first_sentence, overview_chunk, split_text

FIXTURES = Path(__file__).parents[1] / "fixtures"


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(round(seconds, 2))
        self.now += seconds


def make_fetcher(handler, tmp_path: Path, clock: Clock | None = None, **kw) -> Fetcher:
    clock = clock or Clock()
    return Fetcher(
        "test-agent/1.0",
        tmp_path / "cache",
        24,
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock,
        **kw,
    )


def test_fetcher_identifies_itself_and_caches(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers["user-agent"]))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"payload")

    fetcher = make_fetcher(handler, tmp_path)

    assert fetcher.get("https://example.org/data") == b"payload"
    assert fetcher.get("https://example.org/data") == b"payload"
    assert seen == [("/robots.txt", "test-agent/1.0"), ("/data", "test-agent/1.0")]


def test_fetcher_obeys_robots_txt(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private/\n",
                headers={"content-type": "text/plain"},
            )
        return httpx.Response(200, content=b"ok")

    fetcher = make_fetcher(handler, tmp_path)

    assert fetcher.get("https://example.org/public") == b"ok"
    with pytest.raises(FetchError, match="robots.txt disallows"):
        fetcher.get("https://example.org/private/x")


def test_fetcher_waits_out_the_crawl_delay_between_requests(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nCrawl-delay: 30\n", headers={"content-type": "text/plain"}
            )
        return httpx.Response(200, content=request.url.path.encode())

    clock = Clock()
    fetcher = make_fetcher(handler, tmp_path, clock)
    fetcher.get("https://example.org/a")
    fetcher.get("https://example.org/b")

    # The robots.txt request counts too: every later request to the host waits 30 s.
    assert clock.slept == [30.0, 30.0]


def test_fetcher_retries_server_errors_then_gives_up(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(request.url.path)
        return httpx.Response(503)

    with pytest.raises(FetchError, match="kept failing"):
        make_fetcher(handler, tmp_path).get("https://example.org/flaky")
    assert len(calls) == 4


def test_fetcher_sends_per_host_headers(tmp_path):
    keys = []

    def handler(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers.get("apikey"))
        return httpx.Response(404 if request.url.path == "/robots.txt" else 200, content=b"{}")

    fetcher = make_fetcher(handler, tmp_path, headers={"api.example.org": {"apiKey": "k"}})
    fetcher.get("https://api.example.org/cves")

    assert keys[-1] == "k"


def test_ingest_snapshots_with_sha256_and_skips_unchanged_input(tmp_path, monkeypatch):
    yaml_bytes = (FIXTURES / "atlas/ATLAS.yaml").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path.endswith("ATLAS-latest.yaml"):
            return httpx.Response(200, content=b"ATLAS-2026.09.yaml")
        return httpx.Response(200, content=yaml_bytes)

    settings = Settings(data_dir=str(tmp_path / "data"))
    fetcher = make_fetcher(handler, tmp_path)

    first = pipeline.ingest("atlas", settings, fetcher)
    second = pipeline.ingest("atlas", settings, fetcher)

    assert first == "atlas 2026.09: 6 chunks, 5 edges"
    assert second.startswith("atlas 2026.09: unchanged (sha256 ")
    raw = tmp_path / "data/raw/atlas/2026.09"
    assert (raw / "ATLAS.yaml").read_bytes() == yaml_bytes
    assert "ATLAS.yaml" in (raw / "SHA256SUMS").read_text()
    sha, chunks, edges = pipeline.load_processed(settings, "atlas")  # type: ignore[misc]
    assert len(chunks) == 6 and len(edges) == 5 and len(sha) == 64


def test_split_text_breaks_at_paragraphs_and_never_exceeds_the_limit():
    text = "\n\n".join(["a" * 40, "b" * 40, "c" * 40])

    assert split_text(text, 100) == ["a" * 40 + "\n\n" + "b" * 40, "c" * 40]
    assert all(len(p) <= 30 for p in split_text("x" * 95, 30))


def test_finalize_numbers_the_parts_of_each_unit():
    long = chunk("AML.T0051", "\n\n".join(["word " * 20] * 3))
    other = chunk("AML.T0052", "short")

    parts = finalize([long, other], max_chars=150)

    assert [(c.native_id, c.chunk_index) for c in parts] == [
        ("AML.T0051", 0),
        ("AML.T0051", 1),
        ("AML.T0051", 2),
        ("AML.T0052", 0),
    ]
    assert len({c.point_id for c in parts}) == 4


def test_first_sentence_stops_at_the_sentence_end_or_the_limit():
    assert first_sentence("One line\nwrapped. Two. Three?") == "One line wrapped."
    assert first_sentence("word " * 50, max_chars=22) == "word word word word…"


def test_overview_lists_each_entry_once_in_id_order_with_the_source_attribution():
    entries = [
        chunk("ASI02", "Second risk. More.", title="Two"),
        chunk("ASI01", "First risk.", title="One"),
        chunk("ASI01", "A later section.", title="One"),
    ]

    overview = overview_chunk(
        entries, native_id="Top 2", title="Top 2: overview", url="https://x", intro="Risks:"
    )

    assert overview.text == "Risks:\nASI01 One: First risk.\nASI02 Two: Second risk."
    assert (overview.native_id, overview.url, overview.heading_path) == (
        "Top 2",
        "https://x",
        ["Overview"],
    )
    assert (overview.attribution, overview.source_version) == (
        entries[0].attribution,
        entries[0].source_version,
    )
