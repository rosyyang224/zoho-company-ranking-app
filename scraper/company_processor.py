import re
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

from scraper_config import FAKE_CHROME_HEADERS, ACQUISITION_MAP
from bing_search import get_bing_soup, extract_and_score_links, verify_website_fast, check_acquisition_status
from location_utils import parse_contact_page, assign_region
from logging_config import logger

session = requests.Session()
session.headers.update(FAKE_CHROME_HEADERS)

def fetch_page_with_playwright(url: str) -> str:
    """
    If requests.get() returns 403, fall back to Playwright.
    """
    from playwright.sync_api import sync_playwright

    print(f"    🔍 [Playwright] fetching {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(FAKE_CHROME_HEADERS)
        page.goto(url, timeout=15_000)
        page.wait_for_timeout(2_000)
        html = page.content()
        browser.close()
    return html


def fetch_html_with_fallback(url: str) -> tuple[str, BeautifulSoup]:
    """
    Try static requests.get; on HTTP 403, fall back to Playwright.
    Returns (html_text, soup).
    """
    try:
        r = session.get(url, timeout=5)
        r.raise_for_status()
        return r.text, BeautifulSoup(r.text, "html.parser")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            html = fetch_page_with_playwright(url)
            return html, BeautifulSoup(html, "html.parser")
        else:
            raise
    except Exception:
        raise


def find_contact_link(soup: BeautifulSoup, base_url: str) -> str | None:
    """Find a link to the contact page by URL patterns or link text."""
    print("    🔍 Searching for contact page...")
    anchors = soup.select("a[href]")
    abs_links = [urljoin(base_url, a["href"]) for a in anchors]

    # URL path patterns
    contact_paths = [
        "/contact", "/contact-us", "/contact_us", "/contacts",
        "/get-in-touch", "/reach-us", "/about/contact",
        "/company/contact", "/support/contact"
    ]
    for link in abs_links:
        parsed = urlparse(link.lower())
        for pattern in contact_paths:
            if parsed.path.rstrip("/").endswith(pattern):
                print(f"    ✅ Found by path '{pattern}': {link}")
                return link

    # Link text patterns
    for a in anchors:
        txt = a.get_text(strip=True).lower()
        if any(txt == phrase or txt.startswith(phrase) for phrase in [
            "contact", "contact us", "get in touch", "reach us", "office locations"
        ]):
            link = urljoin(base_url, a["href"])
            print(f"    ✅ Found by link text '{txt}': {link}")
            return link

    print("    ❌ No contact link found.")
    return None


def process_company(company_name: str) -> dict:
    print(f"\n{'='*60}")
    print(f"=== Processing '{company_name}' ===")
    print(f"{'='*60}")
    original = company_name

    # Handle acquisitions
    if company_name in ACQUISITION_MAP:
        mapped = ACQUISITION_MAP[company_name]
        print(f"  🔄 Mapped '{company_name}' → '{mapped}' (acquirer)")
        company_name = mapped

    soup = get_bing_soup(company_name)
    if not soup:
        print("  ❌ No Bing results; skipping.")
        return {"company": original, "url": None, "country": None, "state": None, "region": None}

    print("  🧪 Bing result blocks →", len(soup.select("li.b_algo")))
    best_home = extract_and_score_links(soup, company_name)
    if not best_home:
        print("  ❌ No homepage candidate; skipping.")
        return {"company": original, "url": None, "country": None, "state": None, "region": None}

    # Verify homepage
    if not verify_website_fast(best_home, company_name):
        print(f"  🔍 Verification failed for {best_home}; checking acquisition…")
        acq = check_acquisition_status(soup, company_name)
        if acq and acq.get("acquirer"):
            acq_name = acq["acquirer"]
            print(f"  🔍 Re-querying for acquirer '{acq_name}'")
            soup = get_bing_soup(acq_name)
            best_home = extract_and_score_links(soup, acq_name)
            if not best_home or not verify_website_fast(best_home, acq_name):
                print("  ❌ No valid homepage after acquisition fallback.")
                return {"company": original, "url": None, "country": None, "state": None, "region": None}
    else:
        print(f"  ✅ Verified homepage: {best_home}")

    final_url = best_home
    country, state = None, None

    # Location extraction
    try:
        print(f"\n  {'='*40}")
        print("  🌐 LOCATION EXTRACTION START")
        print(f"  {'='*40}")

        # Fetch homepage
        print("  📥 Fetching homepage HTML…")
        homepage_html, soup_home = fetch_html_with_fallback(final_url)

        # Determine page to parse
        contact_link = find_contact_link(soup_home, final_url)
        if contact_link:
            print(f"  📞 Contact page: {contact_link}")
            contact_html, soup_contact = fetch_html_with_fallback(contact_link)
            html_content = contact_html
            lines = soup_contact.get_text(separator="\n").split("\n")
            body_lines = [ln.strip() for ln in lines if ln.strip()]
        else:
            print("  🏠 No contact page; using homepage content")
            html_content = homepage_html
            soup_contact = soup_home
            lines = soup_contact.get_text(separator="\n").split("\n")
            body_lines = [ln.strip() for ln in lines if ln.strip()]


        # Static parse
        print("  🎯 Parsing content for location…")
        country, state = parse_contact_page(soup_contact, html_content, body_lines)
        if country:
            print(f"  🎉 Parsed: country={country}, state={state}")
        elif contact_link:
            # Playwright fallback
            print(f"  🧭 Retrying parse with Playwright…")
            rendered = fetch_page_with_playwright(contact_link)
            soup_rendered = BeautifulSoup(rendered, "html.parser")
            lines = soup_rendered.get_text(separator="\n").split("\n")
            body_lines = [ln.strip() for ln in lines if ln.strip()]
            country, state = parse_contact_page(soup_rendered, rendered, body_lines)
            if country:
                print(f"  🎉 Playwright parsed: country={country}, state={state}")

    except Exception as e:
        logger.error(f"Error during location extraction: {e}")

    # Simplified region assignment: prefer state over country
    region = assign_region(country, state)


    # Final output
    print(f"\n  {'='*50}")
    print(f"  🏁 FINAL: country={country or 'Not Found'}, state={state or 'Not Found'}, region={region}")
    print(f"  {'='*50}\n")

    return {
        "company": original,
        "url": final_url,
        "country": country or "Not Found",
        "state": state or "Not Found",
        "region": region
    }