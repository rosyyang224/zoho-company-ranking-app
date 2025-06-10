'''
company_processor.py

Refactored module to find company website and location with unified fetching,
caching, structured logging, and configuration constants.
'''

import re
from functools import lru_cache
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scraper.scraper_config import FAKE_CHROME_HEADERS, ACQUISITION_MAP
from scraper.bing_search import (
    get_bing_soup,
    extract_and_score_links,
    verify_website_fast
)
from scraper.location_utils import parse_contact_page, assign_region
from scraper.logging_config import logger

# Configuration constants
REQUEST_TIMEOUT = 5  # seconds for HTTP requests
PLAYWRIGHT_TIMEOUT = 15_000  # ms for Playwright page.goto
CONTACT_URL_PATTERNS = [
    "/contact", "/contact-us", "/contact_us", "/contacts",
    "/get-in-touch", "/reach-us", "/about/contact",
    "/company/contact", "/support/contact"
]
CONTACT_TEXT_PHRASES = [
    "contact", "contact us", "get in touch",
    "reach us", "office locations"
]

# Shared session
session = requests.Session()
session.headers.update(FAKE_CHROME_HEADERS)

def fetch_page_with_playwright(url: str) -> str:
    """
    If HTTP fetch gets 403, fall back to Playwright to render JS.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright is required for fallback but not installed.")
        raise

    logger.debug(f"Using Playwright to fetch {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(FAKE_CHROME_HEADERS)
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT)
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    return html


def fetch_html(url: str) -> Tuple[str, BeautifulSoup]:
    """
    Fetch HTML via requests, fallback to Playwright on 403.
    Returns (html_text, BeautifulSoup).
    """
    try:
        logger.debug(f"Fetching URL: {url}")
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        html = r.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logger.warning(f"HTTP 403 on {url}, using Playwright fallback")
            html = fetch_page_with_playwright(url)
        else:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        raise

    return html, BeautifulSoup(html, "html.parser")


def find_contact_link(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Locate a contact-page link by path heuristics or link-text.
    """
    anchors = [
        a for a in soup.select("a[href]")
        if not a["href"].lower().startswith(("javascript:", "mailto:", "tel:", "#"))
    ]
    abs_links = [urljoin(base_url, a["href"]) for a in anchors if a.get("href")]

    # Path-based patterns
    for link in abs_links:
        path = urlparse(link.lower()).path.rstrip("/")
        if any(path.endswith(p) for p in CONTACT_URL_PATTERNS):
            logger.debug(f"Contact found by path: {link}")
            return link

    # Text-based heuristics
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
    """
    Determine the company's homepage URL using Bing and heuristics.
    Handles acquisition mappings and yields a verified HTTPS URL or None.
    """
    original = company_name
    # Acquisition mapping
    if company_name in ACQUISITION_MAP:
        company_name = ACQUISITION_MAP[company_name]
        logger.info(f"Mapped name to acquirer: {company_name}")

    # 1) Bing-sourced candidates
    soup = get_bing_soup(company_name)
    if not soup:
        return None

    for score, link in extract_and_score_links(soup, company_name):
        url = link if link.startswith("http") else f"https://{link}"
        if verify_website_fast(url, company_name):
            return url

    return None


def get_company_location(url: str) -> Tuple[str, str, str]:
    """
    Extract country, state, and region from a company's contact page or homepage.
    """
    # Fetch and pick contact vs homepage
    html, soup = fetch_html(url)
    contact = find_contact_link(soup, url)
    if contact:
        html, soup = fetch_html(contact)

    # Parse lines
    lines = [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]
    country, state = parse_contact_page(soup, html, lines)

    # Playwright fallback if no country
    if not country and contact:
        rendered = fetch_page_with_playwright(contact)
        soup2 = BeautifulSoup(rendered, "html.parser")
        lines2 = [ln.strip() for ln in soup2.get_text("\n").split("\n") if ln.strip()]
        country, state = parse_contact_page(soup2, rendered, lines2)

    region = assign_region(country, state)
    return country or "Not Found", state or "Not Found", region or ""


def process_company(
    company_name: str,
    scrape_website: bool  = True,
    scrape_location: bool = True,
) -> dict:
    """
    If scrape_website is False, skips the website lookup.
    If scrape_location is False, skips the location lookup.
    """
    url = country = state = region = None

    if scrape_website:
        url = get_company_website(company_name)

    if scrape_location and url:
        country, state, region = get_company_location(url)

    return {
        "company": company_name,
        "url":      url,
        "country":  country or "Not Found",
        "state":    state   or "Not Found",
        "region":   region  or "",
    }
