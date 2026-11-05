"""Web pages (`parser: web`): a list of URLs and/or a sitemap's, each page split at its headings.

The fetcher obeys robots.txt and paces each host (`fetch.hosts` in pack.yaml).

config:
  urls: [https://example.org/start]
  sitemap: https://example.org/sitemap.xml      # a sitemap index's sitemaps are read too
  include: [https://example.org/docs/]          # URL prefixes to keep (default: all)
  max_pages: 100                                # (default 100)
  language: en                                  # (default en)
  version: "2026.1"                             # (default: the content's digest)

A page's units are named by its URL's path and query: `docs/install#requirements`."""

import hashlib
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from rag_stack.ingestion.fetch import Fetcher
from rag_stack.ingestion.generic.chunking import (
    document_chunks,
    html_blocks,
    html_title,
    snapshot,
    unstamped,
)
from rag_stack.ingestion.models import Chunk, Edge, Snapshot


def sitemap_urls(fetcher: Fetcher, url: str, seen: set[str] | None = None) -> list[str]:
    """The pages a sitemap lists; each sitemap of an index is read once, even in a cycle."""
    seen = set() if seen is None else seen
    if url in seen:
        return []
    seen.add(url)
    sitemap = BeautifulSoup(fetcher.get(url), "xml")
    locs = [loc.get_text(strip=True) for loc in sitemap.find_all("loc")]
    if sitemap.find("sitemapindex"):
        return [page for nested in locs for page in sitemap_urls(fetcher, nested, seen)]
    return locs


def fetch(fetcher: Fetcher, config: dict[str, Any], retrieved_at: str) -> Snapshot:
    found = list(config.get("urls", []))
    if sitemap := config.get("sitemap"):
        found += sitemap_urls(fetcher, sitemap)
    include = tuple(config.get("include", ()))
    pages = [u for u in dict.fromkeys(found) if not include or u.startswith(include)]
    urls = {
        f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.html": url
        for url in pages[: config.get("max_pages", 100)]
    }
    if not urls:
        raise ValueError(f"{config['id']}: no pages to fetch")
    return snapshot(config, retrieved_at, {n: fetcher.get(u) for n, u in urls.items()}, urls)


def parse(snapshot: Snapshot) -> tuple[list[Chunk], list[Edge]]:
    _, files, common = unstamped(snapshot)
    chunks = []
    for name, content in files.items():
        url = snapshot.urls[name]
        # shortcut: pages of two hosts with the same path share IDs; use one source per host.
        parts = urlsplit(url)
        path = (parts.path.strip("/") or "index") + (f"?{parts.query}" if parts.query else "")
        title = html_title(content) or path.rsplit("/", 1)[-1]
        chunks += document_chunks(path, html_blocks(content), title=title, url=url, **common)
    return chunks, []
