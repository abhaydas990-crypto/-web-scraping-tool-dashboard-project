"""
Entry point. Run from the project root:

    python -m scraper.main                      # scrape everything
    python -m scraper.main --only faculty notices
    python -m scraper.main --delay 2.5
"""
import argparse
import logging

import scraper
from scraper import courses, documents, faculty, notices
from utils.cleaner import clean_dataframe, save_csv

TASKS = {
    "faculty": (faculty, ["name", "email"]),
    "courses": (courses, ["course_name"]),
    "notices": (notices, ["title", "link"]),
    "documents": (documents, ["url"]),
}


def run(only=None):
    scraper.DATA_DIR.mkdir(exist_ok=True)
    summary = {}
    for name, (module, dedupe) in TASKS.items():
        if only and name not in only:
            continue
        logging.info("=== Scraping %s ===", name)
        try:
            rows, columns = module.scrape()
        except Exception:
            logging.exception("%s scraper failed", name)
            continue
        df = clean_dataframe(rows, columns, dedupe_on=dedupe)
        output_path = scraper.DATA_DIR / f"{name}.csv"
        if df.empty and output_path.exists():
            logging.warning("%s returned no rows; keeping existing %s", name, output_path)
            summary[name] = 0
            continue
        save_csv(df, output_path)
        summary[name] = len(df)
    return summary


def main():
    ap = argparse.ArgumentParser(description="RIMS website scraper")
    ap.add_argument("--only", nargs="+", choices=list(TASKS), help="run selected scrapers")
    ap.add_argument("--delay", type=float, default=None, help="seconds between requests")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.delay is not None:
        scraper.DELAY = args.delay
    summary = run(args.only)
    print("\nDone:", ", ".join(f"{k}: {v} rows" for k, v in summary.items()) or "nothing scraped")


if __name__ == "__main__":
    main()
