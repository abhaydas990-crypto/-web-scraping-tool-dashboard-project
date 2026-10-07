"""Notices scraper: finds notice/news/circular pages and extracts title, date, link."""
from urllib.parse import urljoin

from utils.cleaner import extract_date

from scraper import BASE_URL, DOC_EXT, find_section_pages, get_api_pages, get_soup, href_value, log

KEYWORDS = ["notice", "news", "circular", "announcement", "event", "update", "bulletin"]
COLUMNS = ["title", "date", "link", "is_document", "category", "source_url"]
NAV_WORDS = {"home", "about", "contact", "next", "previous", "read more", "more", "login"}


def _category(url):
    u = url.lower()
    for k in ("exam", "admission", "result", "scholarship", "event", "circular", "news"):
        if k in u:
            return k
    return "notice"


def scrape():
    api_records = get_api_pages("notices")
    if api_records is not None:
        rows = []
        for record in api_records:
            pdf = record.get("pdf") or {}
            image = record.get("image") or {}
            link = pdf.get("url") or record.get("link", "") or image.get("url", "")
            category = record.get("noticeCategory") or {}
            rows.append({
                "title": record.get("noticeName", ""),
                "date": extract_date(record.get("createdAt", "")),
                "link": link,
                "is_document": bool(pdf) or link.lower().split("?")[0].endswith(DOC_EXT),
                "category": category.get("title", "notice"),
                "source_url": BASE_URL,
            })
        log.info("notices: %d records from public API", len(rows))
        return rows, COLUMNS

    rows = []
    for page in find_section_pages(KEYWORDS):
        soup = get_soup(page)
        if not soup:
            continue
        count = 0
        # Prefer list/table items so the date next to each link is captured
        for item in soup.find_all(["li", "tr", "article", "div"]):
            if item.find(["li", "tr", "article"]):   # skip containers
                continue
            a = item.find("a", href=True)
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            if len(title) < 8 or title.lower() in NAV_WORDS:
                continue
            link = urljoin(page, href_value(a))
            if not link or link.startswith(("mailto:", "tel:", "javascript:")):
                continue
            date = extract_date(item.get_text(" ", strip=True))
            rows.append({
                "title": title, "date": date, "link": link,
                "is_document": link.lower().split("?")[0].endswith(DOC_EXT),
                "category": _category(page), "source_url": page,
            })
            count += 1
        log.info("notices: %d records from %s", count, page)
    return rows, COLUMNS
