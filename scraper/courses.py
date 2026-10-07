"""Courses scraper: finds programme pages and extracts course name, duration, eligibility."""
import re

from . import BASE_URL, get_api_json, find_section_pages, get_soup, log

KEYWORDS = ["course", "program", "academic", "admission", "department", "stream"]
COLUMNS = ["course_name", "level", "duration", "eligibility", "fees", "description",
           "source_url"]
DEGREE_RE = re.compile(
    r"\b(b\.?\s?sc|m\.?\s?sc|b\.?\s?tech|m\.?\s?tech|b\.?\s?com|m\.?\s?com|b\.?\s?a\b|m\.?\s?a\b|"
    r"bba|mba|bca|mca|b\.?\s?pharm|m\.?\s?pharm|b\.?\s?ed|m\.?\s?ed|diploma|pgdm|"
    r"post[- ]graduate|under[- ]graduate|certificate|nursing|gnm|anm|llb|llm)\b", re.I)
DURATION_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*[- ]?\s*(years?|yrs?|months?|semesters?)\b", re.I)
ELIG_RE = re.compile(r"eligibility\s*[:\-]?\s*(.{5,200})", re.I)
FEES_RE = re.compile(r"(?:fees?|fee structure)\s*[:\-]?\s*((?:rs\.?|inr|₹)\s*[\d,]+[^|]{0,40})", re.I)


def _level(name):
    n = name.lower()
    if re.search(r"\b(m\.?\s?(sc|tech|com|a|pharm|ed)|mba|mca|pgdm|llm|post)", n):
        return "Postgraduate"
    if re.search(r"\b(b\.?\s?(sc|tech|com|a|pharm|ed)|bba|bca|llb|under)", n):
        return "Undergraduate"
    if "diploma" in n or "certificate" in n:
        return "Diploma/Certificate"
    return ""


def _record(name, context, url):
    elig = ELIG_RE.search(context)
    dur = DURATION_RE.search(context) or DURATION_RE.search(name)
    fees = FEES_RE.search(context)
    return {
        "course_name": name,
        "level": _level(name),
        "duration": dur.group(0) if dur else "",
        "eligibility": elig.group(1) if elig else "",
        "fees": fees.group(1) if fees else "",
        "description": context[:300] if context != name else "",
        "source_url": url,
    }


def _from_tables(soup, url):
    rows = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        headers = [c.get_text(" ", strip=True).lower() for c in trs[0].find_all(["th", "td"])]
        if not any(k in " ".join(headers) for k in ("course", "program", "degree")):
            continue
        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            name = next((c for c in cells if DEGREE_RE.search(c)), cells[0])
            rows.append(_record(name, " | ".join(cells), url))
    return rows


def _from_text_blocks(soup, url):
    rows, seen = [], set()
    for el in soup.find_all(["h2", "h3", "h4", "h5", "li", "a", "strong"]):
        if el.name in ("li", "a") and el.find(["h2", "h3", "h4", "h5", "strong"]):
            continue  # the heading inside will be captured instead
        name = el.get_text(" ", strip=True)
        if not (2 < len(name) < 100) or not DEGREE_RE.search(name) or name.lower() in seen:
            continue
        seen.add(name.lower())
        parent = el.find_parent(["div", "li", "section", "article"]) or el
        rows.append(_record(name, parent.get_text(" | ", strip=True), url))
    return rows


def scrape():
    categories = get_api_json("course-categories/get-all")
    if categories is not None and isinstance(categories.get("data"), list):
        rows = []
        api_succeeded = True
        for category in categories["data"]:
            category_id = category.get("id")
            if not category_id:
                continue
            response = get_api_json(f"courses/category/{category_id}")
            if response is None or not isinstance(response.get("data"), list):
                api_succeeded = False
                break
            category_name = category.get("title", "")
            for course in response["data"]:
                name = course.get("courseName", "")
                level = _level(name)
                if not level:
                    category_lower = category_name.lower()
                    if "undergraduate" in category_lower:
                        level = "Undergraduate"
                    elif "postgraduate" in category_lower:
                        level = "Postgraduate"
                    elif "certif" in category_lower or "diploma" in category_lower:
                        level = "Diploma/Certificate"
                    else:
                        level = category_name
                eligibility = course.get("eligibility") or []
                if isinstance(eligibility, list):
                    eligibility = "; ".join(
                        ": ".join(part for part in
                                   (item.get("name", ""), item.get("description", "")) if part)
                        for item in eligibility if isinstance(item, dict)
                    )
                duration = course.get("duration", "")
                if duration != "":
                    duration = str(duration)
                    if re.fullmatch(r"\d+(?:/\d+)?", duration):
                        duration += " year" if duration == "1" else " years"
                rows.append({
                    "course_name": name,
                    "level": level,
                    "duration": duration,
                    "eligibility": eligibility,
                    "fees": "",
                    "description": course.get("description", ""),
                    "source_url": BASE_URL,
                })
        if api_succeeded:
            log.info("courses: %d records from public API", len(rows))
            return rows, COLUMNS

    rows = []
    for url in find_section_pages(KEYWORDS):
        soup = get_soup(url)
        if not soup:
            continue
        found = _from_tables(soup, url) + _from_text_blocks(soup, url)
        log.info("courses: %d records from %s", len(found), url)
        rows.extend(found)
    return rows, COLUMNS
