"""Shared config and HTTP helpers for the RIMS scraper."""
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.rimsedu.ac.in/"
API_BASE_URL = "https://api.rimsedu.ac.in/api/"
USER_AGENT = "Mozilla/5.0 (compatible; RIMSScraper/1.0; educational use)"
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DELAY = 1.5          # seconds between requests (be polite)
TIMEOUT = 20
DOC_EXT = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
            ".css", ".js", ".zip", ".rar", ".mp4", ".mp3")

log = logging.getLogger("rims")
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_cache: dict = {}
_robots = None


def _load_robots():
    global _robots
    if _robots is None:
        _robots = RobotFileParser()
        try:
            r = _session.get(urljoin(BASE_URL, "/robots.txt"), timeout=TIMEOUT)
            _robots.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            _robots.parse([])
    return _robots


def normalize(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/") if urlparse(url).path not in ("", "/") else url


def href_value(tag) -> str:
    """Return the first href value from a tag, even when BeautifulSoup stores it as a list."""
    href = tag.get("href") if hasattr(tag, "get") else None
    if isinstance(href, (list, tuple)):
        href = href[0] if href else ""
    return str(href or "").strip()


def is_file_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(DOC_EXT + SKIP_EXT)


def is_internal(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and \
        p.netloc.replace("www.", "") == urlparse(BASE_URL).netloc.replace("www.", "")


def get_soup(url: str, retries: int = 3):
    """Fetch a page (cached, robots-aware, with retries). Returns BeautifulSoup or None."""
    url = normalize(url)
    if url in _cache:
        return _cache[url]
    if not _load_robots().can_fetch(USER_AGENT, url):
        log.info("Blocked by robots.txt: %s", url)
        return None
    for attempt in range(1, retries + 1):
        try:
            log.info("GET %s", url)
            r = _session.get(url, timeout=TIMEOUT)
            time.sleep(DELAY)
            if r.status_code == 200 and "html" in r.headers.get("Content-Type", ""):
                soup = BeautifulSoup(r.text, "lxml")
                _cache[url] = soup
                return soup
            log.info("Skipping %s (status %s)", url, r.status_code)
            break
        except requests.RequestException as e:
            log.warning("Attempt %d/%d failed for %s: %s", attempt, retries, url, e)
            time.sleep(2 * attempt)
    _cache[url] = None
    return None


def get_api_json(path: str, params=None):
    """Fetch a JSON response from the site's public API, or return None on failure."""
    url = urljoin(API_BASE_URL, path.lstrip("/"))
    try:
        log.info("GET %s", url)
        response = _session.get(
            url, params=params, timeout=TIMEOUT,
            headers={"Accept": "application/json"},
        )
        time.sleep(DELAY)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except (requests.RequestException, ValueError) as e:
        log.warning("API request failed for %s: %s", url, e)
        return None


def get_api_pages(path: str, limit: int = 100):
    """Fetch all pages from a paginated API endpoint, or return None on failure."""
    records = []
    page = 1
    while True:
        payload = get_api_json(path, params={"page": page, "limit": limit})
        if payload is None or not isinstance(payload.get("data"), list):
            return None
        records.extend(payload["data"])
        pagination = payload.get("pagination") or {}
        total_pages = pagination.get("totalPages")
        if total_pages is not None:
            if page >= int(total_pages):
                break
        elif not pagination.get("hasNext"):
            break
        page += 1
    return records


def internal_links(soup, page_url):
    """Yield (text, absolute_url) for each usable internal link on a page."""
    for a in soup.find_all("a", href=True):
        href = href_value(a)
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = normalize(urljoin(page_url, href))
        if is_internal(full):
            yield a.get_text(" ", strip=True), full


def find_section_pages(keywords, max_pages=10, follow_pagination=True):
    """
    Locate pages for a section (faculty, courses, ...) by scanning homepage
    links whose text or URL contains any of the keywords. Also follows
    'next' pagination links.
    """
    home = get_soup(BASE_URL)
    found = []
    if home:
        for text, url in internal_links(home, BASE_URL):
            hay = f"{text} {url}".lower()
            if any(k in hay for k in keywords) and not is_file_url(url):
                if url not in found:
                    found.append(url)
    queue, pages = list(found), []
    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in pages:
            continue
        pages.append(url)
        if follow_pagination:
            soup = get_soup(url)
            if soup:
                for a in soup.find_all("a", href=True):
                    t = a.get_text(strip=True).lower()
                    if t in ("next", "next »", "»", ">") or "next" in (a.get("rel") or []):
                        nxt = normalize(urljoin(url, href_value(a)))
                        if is_internal(nxt) and nxt not in pages and nxt not in queue:
                            queue.append(nxt)
    return pages


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+91[\s-]?)?(?:\d{10}|\d{3,5}[\s-]\d{6,8})")
