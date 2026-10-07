# RIMS Web Scraper

Scrapes https://www.rimsedu.ac.in/ for faculty, courses, notices and downloadable
documents, cleans the data, saves it to CSV and shows it in a Flask dashboard.

```
RIMS-Web-Scraper/
├── scraper/      __init__ (HTTP helpers/config), main, faculty, courses, notices, documents
├── data/         faculty.csv, courses.csv, notices.csv, documents.csv  (generated)
├── dashboard/    app.py  (Flask dashboard), templates/, static/
├── utils/        cleaner.py  (text/date cleaning, dedupe, CSV saving)
├── requirements.txt
└── README.md
```

## Setup
```bash
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run (always from the project root)
```bash
python -m scraper.main                       # scrape everything
python -m scraper.main --only faculty notices
python -m scraper.main --delay 2.5           # slower = gentler on the server
python -m dashboard.app                      # open http://127.0.0.1:5000
```
The dashboard scrapes all four sections when it starts and then every hour.
An open dashboard page reloads every 10 minutes to show updated CSV data. You can
also run a selective scrape from the dashboard.

## How it works
The scraper reads faculty, course, and notice records from the RIMS public JSON
API, then uses static HTML discovery as a fallback. Notice PDF attachments are
also listed as documents. `utils/cleaner.py` normalizes text, converts dates to
YYYY-MM-DD and removes duplicates. Empty runs preserve existing CSV files.

## Tuning for the real site
Extraction is heuristic because page markup differs per site. If a CSV comes out
empty or messy:
1. Edit the `KEYWORDS` list at the top of the relevant module so it matches the site's menu names.
2. Open the page in your browser, right-click, Inspect, and note the CSS classes.
3. Adjust `CARD_CLASS_RE` (faculty) or the selectors in that module's `scrape()`.

## Notes
- Respects `robots.txt`, stays on the same domain, waits between requests.
- The public API is preferred because the site renders its content with JavaScript.
- Check the site's terms of use and avoid overloading the server.
