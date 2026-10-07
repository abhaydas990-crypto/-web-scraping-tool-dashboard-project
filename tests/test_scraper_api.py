import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup

import scraper
from scraper import documents, main, notices
from utils.cleaner import extract_date


class ScraperApiTest(unittest.TestCase):
    def test_api_pages_follows_pagination(self):
        responses = [
            {"data": [{"id": 1}], "pagination": {"totalPages": 2}},
            {"data": [{"id": 2}], "pagination": {"totalPages": 2}},
        ]
        with patch("scraper.get_api_json", side_effect=responses) as get_api_json:
            self.assertEqual(scraper.get_api_pages("faculties"), [{"id": 1}, {"id": 2}])

        self.assertEqual(get_api_json.call_args_list[1].kwargs["params"],
                         {"page": 2, "limit": 100})

    def test_iso_timestamp_converts_to_date(self):
        self.assertEqual(extract_date("2026-09-17T14:13:41.711Z"), "2026-09-17")

    def test_notice_api_maps_pdf_and_timestamp(self):
        record = {
            "noticeName": "Exam schedule",
            "createdAt": "2026-09-17T14:13:41.711Z",
            "pdf": {"url": "https://cdn.example/schedule"},
            "noticeCategory": {"title": "Examination"},
        }
        with patch("scraper.notices.get_api_pages", return_value=[record]):
            rows, _ = notices.scrape()

        self.assertEqual(rows[0]["date"], "2026-09-17")
        self.assertTrue(rows[0]["is_document"])
        self.assertEqual(rows[0]["category"], "Examination")

    def test_document_api_adds_pdf_suffix(self):
        record = {
            "noticeName": "Exam schedule",
            "pdf": {"url": "https://cdn.example/documents/schedule"},
        }
        with patch("scraper.documents.get_api_pages", return_value=[record]):
            rows, _ = documents.scrape()

        self.assertEqual(rows[0]["file_name"], "schedule.pdf")
        self.assertEqual(rows[0]["file_type"], "PDF")

    def test_empty_scrape_preserves_existing_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            csv_path = data_dir / "faculty.csv"
            csv_path.write_text("existing data", encoding="utf-8")
            previous_data_dir = scraper.DATA_DIR
            scraper.DATA_DIR = data_dir
            try:
                with patch.dict(main.TASKS, {"faculty": (SimpleNamespace(
                        scrape=lambda: ([], ["name"])), [])}):
                    main.run(["faculty"])
                self.assertEqual(csv_path.read_text(encoding="utf-8"), "existing data")
            finally:
                scraper.DATA_DIR = previous_data_dir

    def test_internal_links_handles_duplicate_href_values(self):
        soup = BeautifulSoup('<a>Alpha</a>', "lxml")
        soup.a.attrs["href"] = ["/x", "/y"]
        rows = list(scraper.internal_links(soup, scraper.BASE_URL))
        self.assertEqual(rows, [("Alpha", "https://www.rimsedu.ac.in/x")])


if __name__ == "__main__":
    unittest.main()