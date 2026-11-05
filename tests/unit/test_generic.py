"""The no-code sources a pack names by type: a folder of files, web pages, structured records."""

import io
import json
from pathlib import Path

import httpx
import pytest

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.generic import chunking, files, structured, web
from rag_stack.ingestion.models import Edge, Snapshot

RETRIEVED = "2026-11-04T10:00:00+00:00"


def config(tmp_path: Path, **source) -> dict:
    """A source's config as ingest hands it to fetch(): the pack's settings plus the source's."""
    return {
        "id": "docs",
        "license": "CC0-1.0",
        "attribution": "The team, CC0",
        "source_url": "https://example.org/docs",
        "pack_root": str(tmp_path),
        **source,
    }


def offline() -> Fetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"a local source fetched {request.url}")

    return Fetcher("test", Path("/nonexistent"), 0, transport=httpx.MockTransport(handler))


def reparsed(snapshot: Snapshot, module) -> tuple:
    """parse() of the snapshot as reparse rebuilds it from disk: its files and their URLs."""
    files, urls = dict(snapshot.files), dict(snapshot.urls)
    return module.parse(Snapshot(snapshot.source_id, snapshot.version, RETRIEVED, files, urls))


def test_markdown_splits_into_sections_at_its_first_three_heading_levels():
    text = """Intro before any heading.

# Travel

How to travel.

## Hotels

Up to 150 EUR a night.

```
# not a heading: code
```

#### Abroad

Up to 200 EUR.

## Hotels

The second hotels section.
"""
    chunks = chunking.document_chunks(
        "guides/travel.md", chunking.markdown_blocks(text), title="travel", **common()
    )

    assert [(c.native_id, c.title, c.heading_path) for c in chunks] == [
        ("guides/travel.md", "travel", []),
        ("guides/travel.md#travel", "Travel", ["Travel"]),
        ("guides/travel.md#hotels", "Hotels", ["Travel", "Hotels"]),
        ("guides/travel.md#hotels-1", "Hotels", ["Travel", "Hotels"]),
    ]
    # Deeper headings and code stay in their section's text.
    assert "# not a heading: code" in chunks[2].text and "#### Abroad" in chunks[2].text
    # Asking for the document finds each of its sections.
    assert all(c.parent_ids == ["guides/travel.md"] for c in chunks[1:])


def common() -> dict:
    return {
        "source_id": "docs",
        "url": "https://example.org/docs/travel",
        "source_version": "v1",
        "language": "en",
        "retrieved_at": RETRIEVED,
        "license": "CC0-1.0",
        "attribution": "The team, CC0",
    }


def test_html_keeps_the_text_and_headings_and_drops_scripts_and_navigation():
    html = b"""<html><head><title>Expenses</title><script>var x = 1;</script></head>
<body><nav>Home | About</nav><main>
<h1>Expenses</h1><p>Keep every <b>receipt</b>.</p>
<h2 id="limits">Limits</h2><ul><li>Meals: 30 EUR</li><li>Taxi: 50 EUR</li></ul>
</main><footer>Imprint</footer></body></html>"""

    blocks = chunking.html_blocks(html)

    assert blocks == [(1, "Expenses"), (0, "Keep every receipt."), (2, "Limits"),
                      (0, "Meals: 30 EUR\n\nTaxi: 50 EUR")]  # fmt: skip
    assert chunking.html_title(html) == "Expenses"


def write(folder: Path, name: str, content: str | bytes) -> None:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)


def docx(*paragraphs: tuple[str, str]) -> bytes:
    from docx import Document

    document = Document()
    for style, text in paragraphs:
        document.add_paragraph(text, style=style)
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Laptop", "3 years"
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def pdf(*pages: str) -> bytes:
    """A minimal PDF with one line of Helvetica text per page."""
    count = len(pages)
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(count))}] "
        f"/Count {count} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    out, offsets = "%PDF-1.4\n", []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode()


def test_a_folder_of_documents_becomes_one_unit_per_section(tmp_path):
    folder = tmp_path / "docs"
    write(folder, "travel.md", "# Travel\n\nBook early.\n")
    write(folder, "faq/wifi.txt", "The guest network is open.")
    write(folder, "page.html", "<h1>Office</h1><p>Open at 8.</p>")
    write(folder, "policy.docx", docx(("Title", "Devices"), ("Normal", "Lock your screen.")))
    write(folder, "report.pdf", pdf("Revenue grew.", "Costs fell."))
    write(folder, "photo.png", b"\x89PNG")  # not a document: skipped
    cfg = config(tmp_path, url_template="https://example.org/docs/{path}", language="en")

    snapshot = files.fetch(offline(), cfg, RETRIEVED)
    chunks, edges = files.parse(snapshot)

    assert {c.native_id: c.text for c in chunks} == {
        "faq/wifi.txt": "The guest network is open.",
        "page.html#office": "Open at 8.",
        "policy.docx#devices": "Lock your screen.\n\nLaptop | 3 years",
        "report.pdf#page-1": "Revenue grew.",
        "report.pdf#page-2": "Costs fell.",
        "travel.md#travel": "Book early.",
    }
    assert edges == []
    wifi = next(c for c in chunks if c.native_id == "faq/wifi.txt")
    assert wifi.title == "wifi"
    assert wifi.url == "https://example.org/docs/faq/wifi.txt"
    assert (wifi.source_id, wifi.license, wifi.attribution) == ("docs", "CC0-1.0", "The team, CC0")
    assert (wifi.language, wifi.source_version) == ("en", snapshot.version)
    assert len(snapshot.version) == 12  # the content's digest unless the config pins one
    # Parsing needs only the snapshot's files, so `make reparse` rebuilds the same chunks.
    assert reparsed(snapshot, files) == (chunks, edges)


def test_without_a_url_template_documents_link_to_the_source(tmp_path):
    write(tmp_path / "notes", "a.md", "Hello.")

    snapshot = files.fetch(offline(), config(tmp_path, path="notes", version="2026.1"), RETRIEVED)
    (chunk,), _ = files.parse(snapshot)

    assert (chunk.url, chunk.source_version) == ("https://example.org/docs", "2026.1")


def test_a_folder_without_documents_fails_the_ingest(tmp_path):
    (tmp_path / "docs").mkdir()

    with pytest.raises(ValueError, match="no documents"):
        files.fetch(offline(), config(tmp_path), RETRIEVED)


CSV = """term,definition,see_also
Chunk,A retrievable piece of a source.,Embedding; Reranker
Embedding,A vector for a text.,
Reranker,Orders search hits by relevance.,Chunk
"""


def test_csv_records_become_units_and_their_relation_fields_edges(tmp_path):
    write(tmp_path, "glossary.csv", CSV)
    cfg = config(
        tmp_path,
        path="glossary.csv",
        fields={"id": "term", "text": "definition"},
        url_template="https://example.org/glossary#{term}",
        relations=[{"field": "see_also", "rel": "related_to", "split": ";"}],
    )

    snapshot = structured.fetch(offline(), cfg, RETRIEVED)
    chunks, edges = structured.parse(snapshot)

    assert [(c.native_id, c.title, c.text, c.url) for c in chunks] == [
        ("Chunk", "Chunk", "A retrievable piece of a source.", "https://example.org/glossary#Chunk"),
        ("Embedding", "Embedding", "A vector for a text.", "https://example.org/glossary#Embedding"),
        ("Reranker", "Reranker", "Orders search hits by relevance.",
         "https://example.org/glossary#Reranker"),
    ]  # fmt: skip
    assert edges == [
        Edge(src_id="Chunk", rel="related_to", dst_id="Embedding", origin="docs"),
        Edge(src_id="Chunk", rel="related_to", dst_id="Reranker", origin="docs"),
        Edge(src_id="Reranker", rel="related_to", dst_id="Chunk", origin="docs"),
    ]
    assert reparsed(snapshot, structured) == (chunks, edges)


def test_json_records_are_found_by_their_path_and_texts_of_several_fields_are_labeled(tmp_path):
    records = {"data": {"items": [{"sku": 7, "name": "Desk", "size": "160 cm", "tags": ["oak"]}]}}
    write(tmp_path, "products.json", json.dumps(records))
    cfg = config(
        tmp_path,
        path="products.json",
        records="data.items",
        fields={"id": "sku", "title": "name", "text": ["name", "size"]},
        relations=[{"field": "tags", "rel": "tagged"}],
    )

    (chunk,), edges = structured.parse(structured.fetch(offline(), cfg, RETRIEVED))

    assert (chunk.native_id, chunk.title, chunk.url) == ("7", "Desk", "https://example.org/docs")
    assert chunk.text == "name: Desk\n\nsize: 160 cm"
    assert edges == [Edge(src_id="7", rel="tagged", dst_id="oak", origin="docs")]


def test_a_record_without_an_id_fails_the_parse(tmp_path):
    write(tmp_path, "glossary.csv", "term,definition\n,Orphan.\n")
    cfg = config(tmp_path, path="glossary.csv", fields={"id": "term", "text": "definition"})

    with pytest.raises(ValueError, match="record 1 has no term"):
        structured.parse(structured.fetch(offline(), cfg, RETRIEVED))


def site(pages: dict[str, str], tmp_path: Path) -> tuple[Fetcher, list[str]]:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path in pages:
            return httpx.Response(200, content=pages[request.url.path].encode())
        return httpx.Response(404)

    fetcher = Fetcher(
        "test", tmp_path / "cache", 0, min_interval=0, transport=httpx.MockTransport(handler)
    )
    return fetcher, requested


def test_web_pages_come_from_a_sitemap_within_the_included_prefixes(tmp_path):
    loc = "<url><loc>https://example.org/{}</loc></url>"
    fetcher, requested = site(
        {
            "/sitemap.xml": "<sitemapindex><sitemap><loc>https://example.org/docs.xml</loc>"
            "</sitemap></sitemapindex>",
            "/docs.xml": "<urlset>"
            + "".join(loc.format(p) for p in ["docs/a", "docs/b", "docs/c", "blog/x"])
            + "</urlset>",
            "/docs/a": "<title>A page</title><p>Intro.</p><h2>Setup</h2><p>Run it.</p>",
            "/docs/b": "<h1>B</h1><p>Bee.</p>",
            "/start": "<p>Start here.</p>",
        },
        tmp_path,
    )
    cfg = config(
        tmp_path,
        urls=["https://example.org/start"],
        sitemap="https://example.org/sitemap.xml",
        include=["https://example.org/start", "https://example.org/docs/"],
        max_pages=3,
    )

    snapshot = web.fetch(fetcher, cfg, RETRIEVED)
    chunks, _ = web.parse(snapshot)

    assert "/blog/x" not in requested and "/docs/c" not in requested  # excluded, over the cap
    assert [(c.native_id, c.title, c.url) for c in chunks] == [
        ("start", "start", "https://example.org/start"),
        ("docs/a", "A page", "https://example.org/docs/a"),
        ("docs/a#setup", "Setup", "https://example.org/docs/a"),
        ("docs/b#b", "B", "https://example.org/docs/b"),
    ]
    assert reparsed(snapshot, web) == (chunks, [])


def test_a_heading_like_an_earlier_anchor_with_a_suffix_gets_its_own_anchor():
    blocks = [(2, "Foo"), (0, "One."), (2, "Foo"), (0, "Two."), (2, "Foo-1"), (0, "Three.")]

    chunks = chunking.document_chunks("a.md", blocks, title="a", **common())

    assert [c.native_id for c in chunks] == ["a.md#foo", "a.md#foo-1", "a.md#foo-1-1"]


def test_pages_differing_only_in_their_query_are_distinct_units(tmp_path):
    fetcher, _ = site({"/view": "<h1>Entry</h1><p>A page.</p>"}, tmp_path)
    urls = ["https://example.org/view?id=1", "https://example.org/view?id=2"]

    chunks, _ = web.parse(web.fetch(fetcher, config(tmp_path, urls=urls), RETRIEVED))

    assert [c.native_id for c in chunks] == ["view?id=1#entry", "view?id=2#entry"]


def test_a_sitemap_index_naming_itself_is_read_once(tmp_path):
    index = "<sitemapindex><sitemap><loc>https://example.org/sitemap.xml</loc></sitemap>"
    index += "<sitemap><loc>https://example.org/pages.xml</loc></sitemap></sitemapindex>"
    fetcher, requested = site(
        {
            "/sitemap.xml": index,
            "/pages.xml": "<urlset><url><loc>https://example.org/a</loc></url></urlset>",
            "/a": "<p>A.</p>",
        },
        tmp_path,
    )

    snapshot = web.fetch(
        fetcher, config(tmp_path, sitemap="https://example.org/sitemap.xml"), RETRIEVED
    )

    assert list(snapshot.urls.values()) == ["https://example.org/a"]
    assert requested.count("/sitemap.xml") == 1


def test_a_record_id_of_zero_is_an_id_and_a_blank_one_is_not(tmp_path):
    write(tmp_path, "r.json", json.dumps([{"n": 0, "t": "Zero."}, {"n": " ", "t": "Blank."}]))
    cfg = config(tmp_path, path="r.json", fields={"id": "n", "text": "t"})
    snapshot = structured.fetch(offline(), cfg, RETRIEVED)

    with pytest.raises(ValueError, match="record 2 has no n"):
        structured.parse(snapshot)
    write(tmp_path, "r.json", json.dumps([{"n": 0, "t": "Zero."}]))
    (chunk,), _ = structured.parse(structured.fetch(offline(), cfg, RETRIEVED))
    assert chunk.native_id == "0"
