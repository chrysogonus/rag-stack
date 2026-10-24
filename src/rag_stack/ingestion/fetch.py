import hashlib
import json
import logging
import time
import urllib.robotparser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


class Fetcher:
    """A polite HTTP client: identifies itself, obeys robots.txt, rate-limits per host and
    caches responses on disk so re-runs don't hit the sources again."""

    def __init__(
        self,
        user_agent: str,
        cache_dir: Path,
        cache_ttl_hours: float,
        *,
        min_interval: float = 1.0,
        host_intervals: dict[str, float] | None = None,
        headers: dict[str, dict[str, str]] | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
    ) -> None:
        self.user_agent = user_agent
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl_hours * 3600
        self.min_interval = min_interval
        self.host_intervals = host_intervals or {}
        self.host_headers = headers or {}
        self.client = httpx.Client(
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            timeout=60,
            transport=transport,
        )
        self.sleep = sleep
        self.clock = clock
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.last_request: dict[str, float] = {}

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        return self._request("GET", url, params=params, headers=headers)

    def post_json(self, url: str, body: dict[str, Any]) -> bytes:
        return self._request("POST", url, json_body=body)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> bytes:
        key = json.dumps([method, url, params, headers, json_body], sort_keys=True)
        cached = self.cache_dir / hashlib.sha256(key.encode()).hexdigest()
        if cached.exists() and time.time() - cached.stat().st_mtime < self.cache_ttl:
            return cached.read_bytes()

        host = urlsplit(url).netloc
        if not self._allowed(url):
            raise FetchError(f"robots.txt disallows {url}")
        all_headers = {**self.host_headers.get(host, {}), **(headers or {})}
        for attempt in range(4):
            self._wait(host)
            response = self.client.request(
                method, url, params=params, headers=all_headers, json=json_body
            )
            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning("%s %s -> %s, retrying", method, url, response.status_code)
                self.sleep(2**attempt * self._interval(host))
                continue
            if response.status_code != 200:
                raise FetchError(f"{method} {url} -> HTTP {response.status_code}")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(response.content)
            return response.content
        raise FetchError(f"{method} {url} kept failing")

    def _interval(self, host: str) -> float:
        delay = self.robots[host].crawl_delay(self.user_agent) if host in self.robots else None
        return max(float(delay or 0), self.host_intervals.get(host, self.min_interval))

    def _wait(self, host: str) -> None:
        if host in self.last_request:
            remaining = self.last_request[host] + self._interval(host) - self.clock()
            if remaining > 0:
                self.sleep(remaining)
        self.last_request[host] = self.clock()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.netloc not in self.robots:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
            self._wait(parts.netloc)
            response = self.client.get(robots_url)
            # Same rules as urllib: 401/403 forbid everything, other errors allow everything.
            if response.status_code in (401, 403):
                parser.parse(["User-agent: *", "Disallow: /"])
            elif response.status_code < 400 and "text/plain" in response.headers.get(
                "content-type", "text/plain"
            ):
                parser.parse(response.text.splitlines())
            else:
                parser.parse([])
            self.robots[parts.netloc] = parser
        return self.robots[parts.netloc].can_fetch(self.user_agent, url)
