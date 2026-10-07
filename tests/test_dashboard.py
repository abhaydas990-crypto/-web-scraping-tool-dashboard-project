import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from dashboard import app as dashboard


class DashboardRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_path = Path(self.temp_dir.name)
        self.original_data = dashboard.DATA
        dashboard.DATA = self.data_path
        dashboard.app.config.update(TESTING=True)
        pd.DataFrame([
            {"name": "Ada Lovelace", "department": "Mathematics"},
            {"name": "Grace Hopper", "department": "Computer Science"},
        ]).to_csv(self.data_path / "faculty.csv", index=False)
        self.client = dashboard.app.test_client()

    def tearDown(self):
        dashboard.DATA = self.original_data
        self.temp_dir.cleanup()

    def test_index_renders_csv_rows(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ada Lovelace", response.data)
        self.assertIn(b"Grace Hopper", response.data)
        self.assertIn(b'http-equiv="refresh" content="600"', response.data)

    def test_selected_section_hides_other_data_sections(self):
        response = self.client.get("/?section=faculty")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="faculty"', response.data)
        self.assertNotIn(b'id="courses"', response.data)
        self.assertNotIn(b'id="notices"', response.data)
        self.assertNotIn(b'id="documents"', response.data)
        self.assertIn(b"Show all sections", response.data)

    def test_section_selection_survives_search_submission(self):
        response = self.client.get("/?section=faculty")

        self.assertIn(b'name="section" value="faculty"', response.data)

    def test_search_and_department_filter(self):
        response = self.client.get(
            "/?q_faculty=Grace&filter_faculty=Computer%20Science#faculty"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Grace Hopper", response.data)
        self.assertNotIn(b"Ada Lovelace", response.data)

    def test_download_uses_active_filters(self):
        response = self.client.get(
            "/download/faculty?q_faculty=Ada&filter_faculty=Mathematics"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=faculty.csv", response.headers["Content-Disposition"])
        self.assertIn(b"Ada Lovelace", response.data)
        self.assertNotIn(b"Grace Hopper", response.data)

    def test_unknown_download_section_returns_404(self):
        self.assertEqual(self.client.get("/download/unknown").status_code, 404)

    def test_scrape_post_runs_selected_sections(self):
        with patch("dashboard.app.run_scrape", return_value={"faculty": 2}) as run:
            response = self.client.post("/scrape", data={"sections": ["faculty"]})

        self.assertEqual(response.status_code, 302)
        self.assertIn("section=faculty", response.headers["Location"])
        run.assert_called_once_with(["faculty"])

    def test_auto_refresh_runs_all_sections_then_waits_hourly(self):
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.return_value = True

        with patch("dashboard.app.run_scrape", return_value={"faculty": 24}) as run:
            dashboard.auto_refresh_loop(stop_event)

        run.assert_called_once_with()
        stop_event.wait.assert_called_once_with(dashboard.AUTO_REFRESH_SECONDS)


if __name__ == "__main__":
    unittest.main()
