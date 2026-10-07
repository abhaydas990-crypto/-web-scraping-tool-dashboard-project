from scraper import is_file_url


def test_is_file_url_ignores_query_strings():
    assert is_file_url("https://example.com/files/report.pdf?download=1")
    assert is_file_url("https://example.com/assets/logo.png?v=2")
    assert not is_file_url("https://example.com/faculty?dept=cs")
    assert not is_file_url("https://example.com/notice")
