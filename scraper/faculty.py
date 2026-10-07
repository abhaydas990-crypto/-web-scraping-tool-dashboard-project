"""Faculty scraper: finds faculty/staff pages and extracts name, designation, etc."""
import re
from urllib.parse import urljoin

from . import BASE_URL, EMAIL_RE, find_section_pages, get_api_pages, get_soup, log

KEYWORDS = ["faculty", "staff", "teacher", "our-team", "team", "professor", "hod"]
COLUMNS = ["name", "designation", "department", "qualification", "email", "phone",
           "photo_url", "source_url"]
DESIG_RE = re.compile(r"\b(professor|prof\.?|lecturer|principal|director|hod|head of|"
                      r"dean|assistant|associate|coordinator|instructor|registrar)\b", re.I)
QUAL_RE = re.compile(r"\b(ph\.?d|m\.?phil|m\.?tech|b\.?tech|mba|m\.?sc|m\.?a\b|m\.?com|"
                     r"mca|bca|b\.?ed|m\.?ed|net|set)\b", re.I)
CARD_CLASS_RE = re.compile(r"faculty|team|member|staff|teacher|profile|person", re.I)


def _from_tables(soup, url):
    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        headers = [c.get_text(" ", strip=True).lower() for c in trs[0].find_all(["th", "td"])]
        if not any(("name" in h or "faculty" in h) for h in headers):
            continue

        def col(row, *keys):
            for i, h in enumerate(headers):
                if any(k in h for k in keys) and i < len(row):
                    return row[i]
            return ""
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not any(cells):
                continue
            rows.append({
                "name": col(cells, "name", "faculty"),
                "designation": col(cells, "designation", "post", "position"),
                "department": col(cells, "department", "dept", "subject"),
                "qualification": col(cells, "qualification", "degree"),
                "email": col(cells, "email", "mail"),
                "phone": col(cells, "phone", "mobile", "contact"),
                "source_url": url,
            })
    return rows


def _from_cards(soup, url):
    rows, seen = [], set()
    for el in soup.find_all(["div", "li", "article", "section"], class_=CARD_CLASS_RE):
        heading = el.find(["h2", "h3", "h4", "h5", "h6", "strong", "b"])
        if not heading or el.find(["div", "li", "article"], class_=CARD_CLASS_RE):
            continue  # skip wrappers that contain nested cards
        name = heading.get_text(" ", strip=True)
        text = el.get_text(" | ", strip=True)
        if not name or len(name) > 80 or name in seen:
            continue
        seen.add(name)
        img = el.find("img", src=True)
        parts = [p.strip() for p in text.split("|") if p.strip() and p.strip() != name]
        desig = next((p for p in parts if DESIG_RE.search(p) and len(p) < 100), "")
        qual = next((p for p in parts if QUAL_RE.search(p) and len(p) < 120), "")
        email = EMAIL_RE.search(text)
        rows.append({
            "name": name, "designation": desig, "qualification": qual,
            "email": email.group(0) if email else "",
            "photo_url": urljoin(url, img["src"]) if img else "",
            "source_url": url,
        })
    return rows


def scrape():
    api_records = get_api_pages("faculties")
    if api_records is not None:
        rows = []
        for record in api_records:
            subjects = record.get("subjectsTeaching") or record.get("areaOfResearch") or []
            qualifications = record.get("qualification") or []
            photo = record.get("photo") or {}
            rows.append({
                "name": record.get("name", ""),
                "designation": record.get("designation", ""),
                "department": ", ".join(item.get("title", "") for item in subjects),
                "qualification": ", ".join(item.get("title", "") for item in qualifications),
                "email": record.get("email", ""),
                "phone": record.get("phoneNumber", ""),
                "photo_url": photo.get("url", ""),
                "source_url": BASE_URL,
            })
        log.info("faculty: %d records from public API", len(rows))
        return rows, COLUMNS

    rows = []
    for url in find_section_pages(KEYWORDS):
        soup = get_soup(url)
        if not soup:
            continue
        found = _from_tables(soup, url) or _from_cards(soup, url)
        log.info("faculty: %d records from %s", len(found), url)
        rows.extend(found)
    return rows, COLUMNS
