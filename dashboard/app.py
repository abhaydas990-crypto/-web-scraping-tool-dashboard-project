"""Flask dashboard. Run from the project root: python -m dashboard.app"""
from io import BytesIO
from pathlib import Path
from threading import Event, Lock, Thread
from urllib.parse import urlparse

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, send_file, url_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUTO_REFRESH_SECONDS = 60 * 60
_scrape_lock = Lock()

app = Flask(__name__)
app.secret_key = "rims-local-dashboard"

SECTIONS = {
    "faculty": {
        "label": "Faculty",
        "columns": ["name", "designation", "department", "qualification", "email",
                    "phone", "photo_url", "source_url"],
        "filter": "department",
    },
    "courses": {
        "label": "Courses",
        "columns": ["course_name", "level", "duration", "eligibility", "fees",
                    "description", "source_url"],
        "filter": "level",
    },
    "notices": {
        "label": "Notices",
        "columns": ["title", "date", "link", "is_document", "category", "source_url"],
        "filter": None,
    },
    "documents": {
        "label": "Documents",
        "columns": ["title", "file_type", "file_name", "url", "found_on"],
        "filter": "file_type",
    },
}


def run_scrape(sections=None):
    from scraper.main import run

    with _scrape_lock:
        return run(sections)


def auto_refresh_loop(stop_event):
    while not stop_event.is_set():
        try:
            result = run_scrape()
            app.logger.info("Automatic scrape complete: %s", result)
        except Exception:
            app.logger.exception("Automatic scrape failed")
        if stop_event.wait(AUTO_REFRESH_SECONDS):
            return


def load(name: str) -> pd.DataFrame:
    path = DATA / f"{name}.csv"
    try:
        frame = pd.read_csv(path).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        frame = pd.DataFrame(columns=SECTIONS[name]["columns"])
    for column in SECTIONS[name]["columns"]:
        if column not in frame.columns:
            frame[column] = ""
    return frame[SECTIONS[name]["columns"]].copy()


def filter_frame(frame: pd.DataFrame, section: str):
    query = request.args.get(f"q_{section}", "").strip()
    filter_column = SECTIONS[section]["filter"]
    selected = request.args.get(f"filter_{section}", "")
    if query:
        mask = frame.astype(str).apply(
            lambda column: column.str.contains(query, case=False, regex=False, na=False)
        ).any(axis=1)
        frame = frame[mask]
    if filter_column and selected:
        frame = frame[frame[filter_column].astype(str) == selected]
    return frame, query, selected


@app.template_global()
def is_http_url(value: str) -> bool:
    parsed = urlparse(str(value))
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@app.get("/")
def index():
    requested_sections = request.args.getlist("section")
    selected_sections = [name for name in SECTIONS if name in requested_sections]
    if not selected_sections:
        selected_sections = list(SECTIONS)

    datasets = {}
    for name in selected_sections:
        config = SECTIONS[name]
        original = load(name)
        frame, query, selected = filter_frame(original, name)
        filter_column = config["filter"]
        values = sorted(original[filter_column].astype(str).unique()) if filter_column else []
        datasets[name] = {
            **config,
            "rows": frame.to_dict(orient="records"),
            "count": len(frame),
            "query": query,
            "selected": selected,
            "filter_values": [value for value in values if value],
        }
    return render_template("index.html", datasets=datasets, sections=SECTIONS,
                           selected_sections=selected_sections)


@app.get("/download/<section>")
def download(section: str):
    if section not in SECTIONS:
        return "Unknown section", 404
    frame, _, _ = filter_frame(load(section), section)
    output = BytesIO(frame.to_csv(index=False).encode("utf-8-sig"))
    return send_file(output, mimetype="text/csv", as_attachment=True,
                     download_name=f"{section}.csv")


@app.post("/scrape")
def scrape():
    sections = [name for name in request.form.getlist("sections") if name in SECTIONS]
    if not sections:
        flash("Choose at least one section to scrape.", "error")
        return redirect(url_for("index"))

    result = run_scrape(sections)
    summary = ", ".join(f"{SECTIONS[name]['label']}: {count}"
                         for name, count in result.items())
    flash(f"Scrape complete. {summary or 'No data returned.'}", "success")
    return redirect(url_for("index", section=sections))


if __name__ == "__main__":
    stop_event = Event()
    Thread(target=auto_refresh_loop, args=(stop_event,), daemon=True,
           name="rims-auto-scraper").start()
    app.run(host="127.0.0.1", port=5000, debug=False)
