from functools import lru_cache
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from scraper.scraper_config import FAKE_CHROME_HEADERS, ACQUISITION_MAP
from scraper.logging_config import logger
from scraper.location_utils import parse_contact_page, assign_region
from scraper.bing_search import (
    get_bing_soup,
    extract_and_score_links,
    verify_website_fast,
    safe_get_html,
    fetch_page_with_playwright,
)

# Shared session
session = requests.Session()
session.headers.update(FAKE_CHROME_HEADERS)

CONTACT_URL_PATTERNS = [
    "/contact", "/contact-us", "/contact_us", "/contacts",
    "/get-in-touch", "/reach-us", "/about/contact",
    "/company/contact", "/support/contact"
]
CONTACT_TEXT_PHRASES = [
    "contact", "contact us", "get in touch",
    "reach us", "office locations"
]

def resolve_redirected_url(url: str) -> str:
    try:
        r = requests.get(url, headers=FAKE_CHROME_HEADERS, timeout=5, allow_redirects=True)
        return r.url
    except Exception:
        return url

def find_contact_link(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    anchors = [
        a for a in soup.select("a[href]")
        if not a["href"].lower().startswith(("javascript:", "mailto:", "tel:", "#"))
    ]
    abs_links = [urljoin(base_url, a["href"]) for a in anchors if a.get("href")]

    for link in abs_links:
        path = urlparse(link.lower()).path.rstrip("/")
        if any(path.endswith(p) for p in CONTACT_URL_PATTERNS):
            logger.debug(f"Contact found by path: {link}")
            return link

    for a in anchors:
        txt = a.get_text(strip=True).lower()
        if any(txt == phr or txt.startswith(phr) for phr in CONTACT_TEXT_PHRASES):
            link = urljoin(base_url, a["href"])
            logger.debug(f"Contact found by text '{txt}': {link}")
            return link

    logger.debug("No contact link found; default to homepage")
    return None


@lru_cache(maxsize=128)
def get_company_website(company_name: str) -> Optional[str]:
    if company_name in ACQUISITION_MAP:
        company_name = ACQUISITION_MAP[company_name]
        logger.info(f"Mapped name to acquirer: {company_name}")

    soup = get_bing_soup(company_name)
    if not soup:
        return None

    for score, link in extract_and_score_links(soup, company_name):
        url = link if link.startswith("http") else f"https://{link}"
        url = resolve_redirected_url(url)
        if verify_website_fast(url, company_name):
            return url

    return None


def get_company_location(url: str) -> Tuple[str, str, str]:
    def get_soup_from_url(target_url: str) -> Optional[BeautifulSoup]:
        html = safe_get_html(target_url)
        if not html:
            html = fetch_page_with_playwright(target_url)
        return BeautifulSoup(html, "html.parser") if html else None

    soup = get_soup_from_url(url)
    if not soup:
        return "Not Found", "Not Found", ""

    contact_url = find_contact_link(soup, url)
    if contact_url:
        soup = get_soup_from_url(contact_url)

    if not soup:
        return "Not Found", "Not Found", ""

    lines = [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]
    html = soup.encode(formatter="html").decode()
    country, state = parse_contact_page(soup, html, lines)

    if not country and contact_url:
        soup2 = get_soup_from_url(contact_url)
        if soup2:
            lines2 = [ln.strip() for ln in soup2.get_text("\n").split("\n") if ln.strip()]
            html2 = soup2.encode(formatter="html").decode()
            country, state = parse_contact_page(soup2, html2, lines2)

    region = assign_region(country, state)
    return country or "Not Found", state or "Not Found", region or ""


def process_company(
    company_name: str,
    scrape_website: bool = True,
    scrape_location: bool = True,
) -> dict:
    url = country = state = region = None

    if scrape_website:
        url = get_company_website(company_name)

    if scrape_location and url:
        country, state, region = get_company_location(url)

    return {
        "company": company_name,
        "url": url,
        "country": country or "Not Found",
        "state": state or "Not Found",
        "region": region or "",
    }
