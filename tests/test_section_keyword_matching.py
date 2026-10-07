import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from scraper import find_section_pages


class FindSectionPagesTests(unittest.TestCase):
    @patch("scraper.get_soup")
    @patch("scraper.internal_links")
    def test_matches_modern_section_names(self, mock_internal_links, mock_get_soup):
        mock_internal_links.return_value = [
            ("Academics", "https://www.rimsedu.ac.in/academics"),
            ("Faculty Directory", "https://www.rimsedu.ac.in/faculty"),
            ("Notice Board", "https://www.rimsedu.ac.in/notices"),
            ("Downloads", "https://www.rimsedu.ac.in/downloads"),
        ]
        mock_get_soup.return_value = BeautifulSoup("<html><body></body></html>", "lxml")

        pages = find_section_pages(["faculty", "courses", "notices", "documents"])

        self.assertIn("https://www.rimsedu.ac.in/academics", pages)
        self.assertIn("https://www.rimsedu.ac.in/faculty", pages)
        self.assertIn("https://www.rimsedu.ac.in/notices", pages)
        self.assertIn("https://www.rimsedu.ac.in/downloads", pages)


if __name__ == "__main__":
    unittest.main()
