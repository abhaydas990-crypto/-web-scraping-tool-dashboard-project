"""Documents scraper: crawls the site (bounded) and lists every downloadable file."""
import os
from collections import deque
from urllib.parse import unquote, urljoin, urlparse

from scraper import (BASE_URL, DOC_EXT, SKIP_EXT, get_api_pages, get_soup,
                     href_value, internal_links, is_file_url, log, normalize)

COLUMNS = ["title", "file_type", "file_name", "url", "found_on"]


def scrape(max_pages=60):
    api_notices = get_api_pages("notices")
    if api_notices is not None:
        rows, seen_docs = [], set()
        for notice in api_notices:
            pdf = notice.get("pdf") or {}
            url = pdf.get("url", "")
            if not url or url in seen_docs:
                continue
            seen_docs.add(url)
            file_name = unquote(os.path.basename(urlparse(url).path))
            if not file_name:
                file_name = f"{notice.get('noticeName', 'notice')}.pdf"
            elif not file_name.lower().endswith(".pdf"):
                file_name += ".pdf"
            rows.append({
                "title": notice.get("noticeName", "") or file_name,
                "file_type": "PDF",
                "file_name": file_name,
                "url": url,
                "found_on": BASE_URL,
            })
        log.info("documents: %d notice files from public API", len(rows))
        return rows, COLUMNS

    rows, seen_docs = [], set()
    queue, visited = deque([normalize(BASE_URL)]), set()
    while queue and len(visited) < max_pages:
        page = queue.popleft()
        if page in visited:
            continue
        visited.add(page)
        soup = get_soup(page)
        if not soup:
            continue
        for a in soup.find_all("a", href=True):
            href = href_value(a)
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            full = urljoin(page, href)
            path = urlparse(full).path.lower()
            if path.endswith(DOC_EXT) and full not in seen_docs:
                seen_docs.add(full)
                fname = unquote(os.path.basename(urlparse(full).path))
                rows.append({
                    "title": a.get_text(" ", strip=True) or fname,
                    "file_type": os.path.splitext(fname)[1].lstrip(".").upper(),
                    "file_name": fname, "url": full, "found_on": page,
                })
        for _, link in internal_links(soup, page):
            if link not in visited and not is_file_url(link):
                queue.append(link)
    log.info("documents: %d files across %d pages", len(rows), len(visited))
    return rows, COLUMNS
