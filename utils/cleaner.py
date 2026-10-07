"""Cleaning helpers shared by all scrapers."""
import re
import unicodedata
from datetime import datetime

import pandas as pd

DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y",
                "%B %d %Y", "%b %d %Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y")
DATE_RE = re.compile(
    r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{4}|"
    r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})(?=\b|T)")


def clean_text(value) -> str:
    """Normalize unicode and collapse whitespace."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value))
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip(" \t\n\r|-–—:")


def extract_date(text: str) -> str:
    """Find the first date in text and return it as YYYY-MM-DD ('' if none)."""
    m = DATE_RE.search(text or "")
    if not m:
        return ""
    raw = m.group(1).replace(",", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def clean_dataframe(rows, columns, dedupe_on=None) -> pd.DataFrame:
    """Rows (list of dicts) -> cleaned, de-duplicated DataFrame with fixed columns."""
    df = pd.DataFrame(rows)
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    df = df[columns].copy()
    for c in columns:
        df[c] = df[c].map(clean_text)
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    df = df.drop_duplicates(subset=dedupe_on or columns).reset_index(drop=True)
    return df


def save_csv(df: pd.DataFrame, path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")
