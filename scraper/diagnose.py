"""
Quick health check of the target site. Run from the project root:

    python -m scraper.diagnose
"""
import requests
from bs4 import BeautifulSoup

from scraper import BASE_URL, USER_AGENT

DOC_EXT = (".pdf", ".doc", ".docx", ".xls", ".xlsx")


def try_fetch(label, **kwargs):
    print(f"\n--- {label} ---")
    try:
        r = requests.get(BASE_URL, timeout=20, **kwargs)
    except requests.exceptions.SSLError as e:
        print("SSL ERROR (certificate problem):", str(e)[:200])
        return None
    except requests.exceptions.RequestException as e:
        print(f"REQUEST FAILED: {type(e).__name__}: {str(e)[:200]}")
        return None
    print("Status:", r.status_code, "| Final URL:", r.url)
    print("Content-Type:", r.headers.get("Content-Type"))
    print("Bytes received:", len(r.content))
    return r


def main():
    r = try_fetch("Scraper user-agent", headers={"User-Agent": USER_AGENT})
    if r is None or r.status_code != 200:
        r2 = try_fetch("Browser-like user-agent", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
        if r2 is None:
            r2 = try_fetch("Without SSL verification (testing only)", verify=False,
                           headers={"User-Agent": USER_AGENT})
        r = r2 or r
    if r is None:
        print("\nRESULT: could not reach the site. Check internet/VPN/firewall.")
        return

    soup = BeautifulSoup(r.text, "lxml")
    links = soup.select("a[href]")
    print("\nTitle:", soup.title.get_text(strip=True) if soup.title else "NO TITLE")
    print("Links found:", len(links))
    print("Scripts:", len(soup.find_all("script")), "| Visible text chars:",
          len(soup.get_text(" ", strip=True)))
    print("Document links on homepage:",
          sum(1 for a in links if (a.get("href") or "").lower().split("?")[0].endswith(DOC_EXT)))
    print("\nFirst 25 menu/links:")
    for a in links[:25]:
        href = (a.get("href") or "")
        print("  ", a.get_text(" ", strip=True)[:40].ljust(40), str(href)[:80])

    print("\nDIAGNOSIS:")
    if r.status_code in (403, 406, 429):
        print("- Site is blocking the request (status %d). Try slower --delay or a browser UA." % r.status_code)
    elif len(links) < 5:
        print("- Very few links: the page is probably built with JavaScript. A Playwright version is needed.")
    else:
        print("- Page fetched fine. Scraper failure is in keyword matching: send me the link list above.")


if __name__ == "__main__":
    main()
