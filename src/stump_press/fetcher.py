"""Chronicling America / loc.gov JSON fetcher (polite, no API key)."""

from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator

from stump_press.local_crumbs import detect_local_crumbs
from stump_press.models import PageCandidate
from stump_press.scorer import score_ocr

USER_AGENT = (
    "stump-press/0.1 (+https://github.com/cmiedema25-rgb/stump-press; "
    "research tool; polite small-volume requests)"
)
SEARCH_URL = "https://www.loc.gov/collections/chronicling-america/"
DEFAULT_PAUSE_S = 0.4


class LocClient:
    def __init__(self, pause_s: float = DEFAULT_PAUSE_S, timeout: float = 60.0, retries: int = 3):
        self.pause_s = pause_s
        self.timeout = timeout
        self.retries = retries
        self._last_request = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.pause_s:
            time.sleep(self.pause_s - elapsed)
        self._last_request = time.monotonic()

    def _open(self, url: str, accept: str | None = None) -> bytes:
        headers = {"User-Agent": USER_AGENT}
        if accept:
            headers["Accept"] = accept
        last_err: Exception | None = None
        for attempt in range(self.retries):
            self._throttle()
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    # Read in chunks to survive flaky connections better
                    chunks: list[bytes] = []
                    while True:
                        block = resp.read(64 * 1024)
                        if not block:
                            break
                        chunks.append(block)
                    return b"".join(chunks)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, http.client.IncompleteRead, ConnectionError, OSError) as exc:
                last_err = exc
                # IncompleteRead sometimes still has partial .partial
                if isinstance(exc, http.client.IncompleteRead) and exc.partial:
                    return bytes(exc.partial)
                time.sleep(0.6 * (attempt + 1))
        assert last_err is not None
        raise last_err

    def get_json(self, url: str) -> Any:
        raw = self._open(url, accept="application/json")
        return json.loads(raw.decode("utf-8", errors="replace"))

    def get_text(self, url: str) -> str:
        return self._open(url).decode("utf-8", errors="replace")

    def download_bytes(self, url: str) -> bytes:
        return self._open(url)


def _parse_lccn(page_id_or_url: str) -> str:
    m = re.search(r"(sn\d{8}|[a-z]{1,3}\d{6,10})", page_id_or_url, re.I)
    return m.group(1) if m else ""


def make_page_id(url: str) -> str:
    """Stable short id from a loc.gov resource URL."""
    m = re.search(
        r"/resource/([^/?]+)/(\d{4}-\d{2}-\d{2})/ed-(\d+)/.*?[?&]sp=(\d+)",
        url,
    )
    if m:
        return f"{m.group(1)}_{m.group(2)}_ed{m.group(3)}_p{m.group(4)}"
    digest = re.sub(r"[^a-zA-Z0-9]+", "_", url)[-80:].strip("_")
    return digest or "page"


def search_pages(
    client: LocClient,
    *,
    year_start: int = 1850,
    year_end: int = 1910,
    limit: int = 20,
    query: str | None = None,
    state: str | None = None,
    front_pages_only: bool = False,
) -> list[dict[str, Any]]:
    """Search loc.gov Chronicling America at page display level."""
    params: list[tuple[str, str]] = [
        ("fo", "json"),
        ("dl", "page"),
        ("c", str(min(max(limit, 1), 100))),
        ("sp", "1"),
        ("dates", f"{year_start}/{year_end}"),
    ]
    if query:
        params.append(("qs", query))
    if state:
        params.append(("location_state", state))
    if front_pages_only:
        params.append(("front_pages_only", "true"))

    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    data = client.get_json(url)
    return list(data.get("results") or [])


def fetch_page_detail(client: LocClient, page_url: str) -> dict[str, Any]:
    """Fetch resource JSON for a single page (adds fo=json)."""
    url = page_url.replace("http://", "https://")
    parsed = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(parsed.query)
    q["fo"] = ["json"]
    new_q = urllib.parse.urlencode({k: v[0] for k, v in q.items()})
    full = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment)
    )
    return client.get_json(full)


def extract_fulltext_url(detail: dict[str, Any]) -> str | None:
    for key in ("fulltext_service",):
        v = detail.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    resource = detail.get("resource") or {}
    if isinstance(resource, dict):
        v = resource.get("fulltext_file")
        if isinstance(v, str) and v.startswith("http"):
            return v
    resources = detail.get("resources") or []
    if resources and isinstance(resources[0], dict):
        v = resources[0].get("fulltext_file")
        if isinstance(v, str) and v.startswith("http"):
            return v
    seg = detail.get("segment_id")
    if isinstance(seg, str) and seg:
        return (
            "https://tile.loc.gov/text-services/word-coordinates-service?"
            + urllib.parse.urlencode(
                {"segment": seg, "format": "alto_xml", "full_text": "1"}
            )
        )
    return None


def fetch_ocr_text(client: LocClient, fulltext_url: str) -> str:
    data = client.get_json(fulltext_url)
    if isinstance(data, dict):
        for _k, v in data.items():
            if isinstance(v, dict) and isinstance(v.get("full_text"), str):
                return v["full_text"]
            if isinstance(v, str) and len(v) > 40:
                return v
        if isinstance(data.get("full_text"), str):
            return data["full_text"]
    return ""


def pick_image_urls(result: dict[str, Any], detail: dict[str, Any] | None = None) -> list[str]:
    urls: list[str] = []
    for src in (result, (detail or {}).get("item") or {}, detail or {}):
        if not isinstance(src, dict):
            continue
        iu = src.get("image_url")
        if isinstance(iu, list):
            urls.extend(u for u in iu if isinstance(u, str))
        elif isinstance(iu, str):
            urls.append(iu)
    resource = (detail or {}).get("resource") or {}
    if isinstance(resource, dict) and isinstance(resource.get("image"), str):
        urls.append(resource["image"])
    dedup: list[str] = []
    seen: set[str] = set()
    for u in urls:
        base = u.split("#")[0]
        if base not in seen:
            seen.add(base)
            dedup.append(u)
    return dedup


def result_to_candidate(
    client: LocClient,
    result: dict[str, Any],
    *,
    fetch_ocr: bool = True,
) -> PageCandidate:
    page_url = result.get("url") or result.get("id") or ""
    if page_url.startswith("http://"):
        page_url = "https://" + page_url[len("http://") :]
    pid = make_page_id(page_url)
    title = result.get("title") or "Untitled page"
    date = result.get("date") or ""
    lccn = ""
    if isinstance(result.get("number_lccn"), list) and result["number_lccn"]:
        lccn = str(result["number_lccn"][0])
    else:
        lccn = _parse_lccn(page_url)

    image_urls = pick_image_urls(result)
    ocr = ""
    fulltext_url = None
    detail = None
    if fetch_ocr and page_url:
        try:
            detail = fetch_page_detail(client, page_url)
            fulltext_url = extract_fulltext_url(detail)
            image_urls = pick_image_urls(result, detail) or image_urls
            if fulltext_url:
                ocr = fetch_ocr_text(client, fulltext_url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError, OSError, http.client.IncompleteRead):
            pass

    scored = score_ocr(ocr)
    hits, crumb_bonus = detect_local_crumbs(ocr)
    reasons = list(scored.reasons)
    if hits:
        reasons.append("local_crumb_language")
    rank_score = min(1.0, scored.score + crumb_bonus)
    metrics = dict(scored.metrics)
    metrics["local_crumb_bonus"] = crumb_bonus
    metrics["ocr_junk_score"] = scored.score
    return PageCandidate(
        id=pid,
        title=title,
        date=date,
        lccn=lccn,
        page_url=page_url,
        image_url=image_urls[0] if image_urls else None,
        image_urls=image_urls,
        ocr_text=ocr,
        ocr_excerpt=(ocr[:800] if ocr else ""),
        score=rank_score,
        reasons=reasons,
        metrics=metrics,
        fulltext_url=fulltext_url,
        local_crumb_hits=hits,
        local_crumb_bonus=crumb_bonus,
    )


def hunt(
    *,
    year_start: int = 1850,
    year_end: int = 1910,
    limit: int = 20,
    query: str | None = None,
    state: str | None = None,
    min_score: float = 0.0,
    client: LocClient | None = None,
    fetch_ocr: bool = True,
) -> list[PageCandidate]:
    """Live hunt: search pages, fetch OCR, score, return sorted junkiest first."""
    client = client or LocClient()
    # Default keyword nudges toward local-notice pages (override with --query)
    search_query = query if query is not None else "society"
    search_n = min(max(limit, 1), 25)
    results = search_pages(
        client,
        year_start=year_start,
        year_end=year_end,
        limit=search_n,
        query=search_query,
        state=state,
    )
    candidates: list[PageCandidate] = []
    for r in results:
        cand = result_to_candidate(client, r, fetch_ocr=fetch_ocr)
        if cand.score >= min_score:
            candidates.append(cand)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]


def iter_fixture_results(path: str) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        yield from data
    elif isinstance(data, dict) and "results" in data:
        yield from data["results"]
