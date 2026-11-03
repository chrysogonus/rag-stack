import json
from pathlib import Path

import httpx
import pytest
from fakes.embeddings import chunk

from rag_stack.config import Settings
from rag_stack.ingestion import pipeline
from rag_stack.ingestion.fetch import Fetcher, FetchError
from rag_stack.ingestion.models import finalize, first_sentence, overview_chunk, split_text
from rag_stack.pack import Credential, Fetch, Host

FIXTURES = Path(__file__).parents[2] / "packs/cybersecurity/tests/fixtures"


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


def test_fetcher_follows_the_next_link_through_every_page_and_caches_it(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        seen.append(str(request.url))
        if "after" in request.url.params:
            return httpx.Response(200, content=b"[2]")
        next_page = '<https://api.example.org/items?q=1&after=c1>; rel="next"'
        return httpx.Response(200, content=b"[1]", headers={"link": next_page})

    fetcher = make_fetcher(handler, tmp_path)
    pages = fetcher.get_pages("https://api.example.org/items", params={"q": 1})

    assert pages == [b"[1]", b"[2]"]
    assert seen == [
        "https://api.example.org/items?q=1",
        "https://api.example.org/items?q=1&after=c1",
    ]
    assert fetcher.get_pages("https://api.example.org/items", params={"q": 1}) == pages
    assert len(seen) == 2


def test_the_fetcher_follows_the_packs_hosts_and_credentials(use_pack, monkeypatch, tmp_path):
    token = Credential(env="EXAMPLE_TOKEN", header="Authorization", value="Bearer {}", interval=1)
    use_pack(
        fetch=Fetch(
            user_agent="notes-bot/1.0",
            hosts={
                "api.example.org": Host(interval=10, credential=token),
                "slow.example.org": Host(interval=5),
            },
        )
    )
    monkeypatch.setenv("EXAMPLE_TOKEN", "t")

    fetcher = pipeline.make_fetcher(Settings(data_dir=str(tmp_path)))

    assert fetcher.user_agent == "notes-bot/1.0"
    assert fetcher.host_headers == {"api.example.org": {"Authorization": "Bearer t"}}
    assert fetcher.host_intervals == {"api.example.org": 1, "slow.example.org": 5}


def test_a_credential_can_come_from_the_env_file(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("GITHUB_TOKEN=t\n")
    monkeypatch.setitem(Settings.model_config, "env_file", str(tmp_path / ".env"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("NVD_API_KEY", raising=False)

    fetcher = pipeline.make_fetcher(Settings(data_dir=str(tmp_path)))

    # The cybersecurity pack: GitHub's API is faster with a token; NVD without a key is slow.
    assert fetcher.host_headers == {"api.github.com": {"Authorization": "Bearer t"}}
    assert fetcher.host_intervals == {"services.nvd.nist.gov": 6.5, "api.github.com": 1.0}


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

    assert first == "atlas 2026.09: 6 chunks, 6 edges"
    assert second.startswith("atlas 2026.09: unchanged (sha256 ")
    raw = tmp_path / "data/raw/atlas/2026.09"
    assert (raw / "ATLAS.yaml").read_bytes() == yaml_bytes
    assert "ATLAS.yaml" in (raw / "SHA256SUMS").read_text()
    sha, chunks, edges = pipeline.load_processed(settings, "atlas")  # type: ignore[misc]
    assert len(chunks) == 6 and len(edges) == 6 and len(sha) == 64


def ingest_atlas_fixture(tmp_path: Path) -> Settings:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path.endswith("ATLAS-latest.yaml"):
            return httpx.Response(200, content=b"ATLAS-2026.09.yaml")
        return httpx.Response(200, content=(FIXTURES / "atlas/ATLAS.yaml").read_bytes())

    settings = Settings(data_dir=str(tmp_path / "data"))
    pipeline.ingest("atlas", settings, make_fetcher(handler, tmp_path))
    return settings


def test_reparse_rebuilds_the_latest_snapshot_offline_into_the_same_chunks_and_edges(tmp_path):
    settings = ingest_atlas_fixture(tmp_path)
    _, chunks, edges = pipeline.load_processed(settings, "atlas")  # type: ignore[misc]

    assert pipeline.reparse("atlas", settings) == ("2026.09", chunks, edges)


def test_reparse_hands_the_parser_its_files_in_fetch_order(tmp_path, monkeypatch):
    from types import SimpleNamespace

    raw = tmp_path / "data/raw/eu-ai-act/v1"
    raw.mkdir(parents=True)
    (tmp_path / "data/processed/eu-ai-act").mkdir(parents=True)
    (tmp_path / "data/processed/eu-ai-act/LATEST").write_text("v1")
    fetched = ["en.xhtml", "de.xhtml", "extra.txt"]  # extra.txt was fetched without a URL
    for name in fetched:
        (raw / name).write_text(name)
    (raw / "SHA256SUMS").write_text("".join(f"0  {n}\n" for n in sorted(fetched)))
    urls = {"en.xhtml": "https://e/en", "de.xhtml": "https://e/de"}
    (raw / "manifest.json").write_text(
        json.dumps({"version": "v1", "retrieved_at": "2026-01-01", "urls": urls})
    )
    seen = []

    def parse(snapshot):
        seen.extend(snapshot.files)
        return [], []

    monkeypatch.setattr(pipeline, "source_module", lambda _: SimpleNamespace(parse=parse))

    pipeline.reparse("eu-ai-act", Settings(data_dir=str(tmp_path / "data")))

    assert seen == fetched


def test_reparse_command_prints_the_sha256_of_the_files_ingest_wrote(tmp_path, monkeypatch, capsys):
    import hashlib

    from rag_stack import cli

    ingest_atlas_fixture(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    processed = tmp_path / "data/processed/atlas/2026.09"

    def sha(name: str) -> str:
        return hashlib.sha256((processed / name).read_bytes()).hexdigest()

    assert cli.main(["reparse", "atlas"]) == 0
    assert capsys.readouterr().out == (
        f"atlas 2026.09: 6 chunks {sha('chunks.jsonl')}, 6 edges {sha('edges.jsonl')}\n"
    )


def test_a_parser_is_fingerprinted_with_the_pack_modules_it_borrows_from():
    import hashlib

    from packs.cybersecurity import ids, laws
    from packs.cybersecurity.parsers import atlas, capec, cwe, eu_law, gesetze_im_internet

    def sha(*modules):
        code = b"".join(Path(str(m.__file__)).read_bytes() for m in modules)
        return hashlib.sha256(code).hexdigest()

    pack = "packs.cybersecurity."
    assert pipeline.parser_sha(atlas, pack) == sha(atlas)
    # CWE uses CAPEC's text helpers: a fix there re-parses CWE too.
    assert pipeline.parser_sha(cwe, pack) == sha(capec, cwe)
    assert pipeline.parser_sha(eu_law, pack) == sha(laws, eu_law)
    assert pipeline.parser_sha(gesetze_im_internet, pack) == sha(ids, gesetze_im_internet)


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
