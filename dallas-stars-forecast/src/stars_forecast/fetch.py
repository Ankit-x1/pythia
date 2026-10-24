"""HTTP fetching with caching, bounded retries and a source manifest.

Rules implemented here (see AGENTS.md):
  * every successful download is cached unchanged under data/raw/;
  * repeated runs reuse the cache instead of re-downloading;
  * request rate is throttled and retries are bounded - never an infinite loop;
  * credentials are never written to disk or logs.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .paths import RAW, rel

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 stars-forecast/0.2 (academic project)"
)

_MIN_INTERVAL = 0.15  # seconds between requests to a host
_last_call: dict[str, float] = {}


class FetchError(RuntimeError):
    """Raised when a bounded retry budget is exhausted."""


@dataclass
class Manifest:
    """Append-only record of every source file used in the build."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    path: Path = RAW / "source_manifest.json"

    def add(self, **kw: Any) -> None:
        self.entries.append(kw)

    def save(self) -> None:
        payload = {
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_files": len(self.entries),
            "files": self.entries,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _throttle(host: str) -> None:
    now = time.monotonic()
    last = _last_call.get(host, 0.0)
    if now - last < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - (now - last))
    _last_call[host] = time.monotonic()


def _get(url: str, *, retries: int = 3, timeout: int = 30) -> requests.Response:
    host = url.split("/")[2]
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        _throttle(host)
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if resp.status_code == 200:
                return resp
            last_err = FetchError(f"HTTP {resp.status_code} for {url}")
            if resp.status_code in (400, 401, 403, 404):
                raise last_err  # do not hammer a permanent rejection
        except requests.RequestException as exc:  # transient network issue
            last_err = exc
        time.sleep(0.6 * attempt)
    raise FetchError(f"failed after {retries} attempts: {url} ({last_err})")


def fetch_text(url: str, raw_subdir: str, fname: str, manifest: Manifest,
               dataset: str, **meta: Any) -> str:
    """Return text content, downloading only when not already cached."""
    dest = RAW / raw_subdir / fname
    if dest.exists():
        text = dest.read_text(encoding="utf-8", errors="replace")
        _record(manifest, dest, url, dataset, cached=True, **meta)
        return text
    resp = _get(url)
    resp.encoding = resp.encoding or "utf-8"
    text = resp.text
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    _record(manifest, dest, url, dataset, cached=False, **meta)
    return text


def fetch_json(url: str, raw_subdir: str, fname: str, manifest: Manifest,
               dataset: str, **meta: Any) -> Any:
    return json.loads(fetch_text(url, raw_subdir, fname, manifest, dataset, **meta))


def _record(manifest: Manifest, dest: Path, url: str, dataset: str,
            cached: bool, **meta: Any) -> None:
    blob = dest.read_bytes()
    manifest.add(
        dataset=dataset,
        file=rel(dest),
        source_url=url,
        retrieved_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        from_cache=cached,
        bytes=len(blob),
        sha256=hashlib.sha256(blob).hexdigest(),
        **meta,
    )
