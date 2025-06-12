import re
import time
import requests
from requests.exceptions import SSLError
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from scraper.scraper_config import FAKE_CHROME_HEADERS, SKIP_DOMAINS, BIOTECH_TERMS

session = requests.Session()
session.headers.update(FAKE_CHROME_HEADERS)

def safe_get_html(url: str, use_playwright_on_403: bool = True) -> str | None:
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 403 and use_playwright_on_403:
            print(f"    🚫 403 for {url}, retrying with Playwright…")
            return fetch_page_with_playwright(url)
        elif r.ok:
            return r.text
    except SSLError as ssl_err:
        # Retry with www prefix if missing
        parsed = urlparse(url)
        if not parsed.netloc.startswith("www."):
            www_url = urlunparse(parsed._replace(netloc=f"www.{parsed.netloc}"))
            print(f"    ⚠️ SSL error, retrying with www: {www_url}")
            try:
                r = requests.get(www_url, timeout=5)
                if r.ok:
                    return r.text
            except Exception as e2:
                print(f"    ❌ retry w/ www failed: {e2}")
        print(f"    ❌ SSL error for {url}: {ssl_err}")
    except Exception as e:
        print(f"    ❌ request error for {url}: {e}")
    return None

def fetch_page_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright
    print(f"    🔍 [Playwright] fetching {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers(FAKE_CHROME_HEADERS)
        page.goto(url, timeout=15_000)
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    return html

def try_url_with_playwright_fallback(url: str, company_name: str) -> bool:
    content = safe_get_html(url)
    if content:
        for tok in extract_simple_tokens(company_name):
            if tok in content.lower():
                return True
    return False

def guess_possible_domains(name):
    name_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    name_clean = re.sub(r'\s+', ' ', name_clean).strip()
    name_lower = name_clean.lower()
    base = re.sub(r'\W+', '', name_lower)
    guesses = [f"{base}.com"]

    if "therapeutics" in name_lower:
        prefix = re.sub(r"[ -]?therapeutics", "", name_lower).replace(" ", "")
        guesses += [f"{prefix}tx.com", f"{prefix}-tx.com", f"{prefix}.com", f"{prefix}therapeutics.com"]

    if any(x in name_lower for x in ["biosciences", "biotech", "biotherapeutics"]):
        prefix = re.sub(r"[ -]?(biosciences|biotech|biotherapeutics)", "", name_lower).replace(" ", "")
        guesses += [f"{prefix}bio.com", f"{prefix}-bio.com", f"{prefix}.com"]

    tokens = name_lower.split()
    if "therapeutics" in tokens:
        dash_prefix = "-".join(t for t in tokens if t != "therapeutics").replace(" ", "")
        guesses += [f"{dash_prefix}-tx.com", f"{dash_prefix}tx.com"]

    return list(dict.fromkeys(guesses))

def fetch_bing_results(query: str, timeout: int = 5):
    url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
    try:
        print(f"  🔍 fetch_bing_results: {query}")
        r = session.get(url, timeout=timeout)
        if r.status_code == 429:
            print("    🚫 Rate‐limited by Bing; sleeping 10s…")
            time.sleep(10)
            r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        print(f"    ❌ fetch_bing_results error: {e}")
        return None

def get_bing_soup(company_name: str):
    domains = guess_possible_domains(company_name)
    print("  🔍 Trying direct domain guesses...")
    for domain in domains:
        test_url = f"https://{domain}"
        content = safe_get_html(test_url)
        if content:
            print(f"  ✅ Direct domain valid: {test_url}")
            return BeautifulSoup(f'<a href="{test_url}">{test_url}</a>', "html.parser")

    for domain in domains:
        query = f"{company_name} site:{domain}"
        print(f"  🔍 Trying forced Bing query: '{query}'")
        soup = fetch_bing_results(query)
        if soup and soup.select_one("li.b_algo"):
            print(f"  ✅ Bing result found for forced query: {domain}")
            return soup

    print(f"  🔍 Trying generic Bing search: '{company_name}'")
    soup = fetch_bing_results(company_name)
    if soup:
        result_blocks = soup.select("li.b_algo")
        if result_blocks:
            domains_seen = [urlparse(a.get("href", "")).netloc.lower() for a in soup.select("li.b_algo h2 a") if a and a.get("href")]
            if all(any(skip in d for skip in SKIP_DOMAINS) for d in domains_seen):
                print("    ⚠️ All generic results are from SKIP_DOMAINS → skipping soup.")
                return None

    if soup and soup.select_one("li.b_algo"):
        print("  ✅ Generic Bing results accepted")
        return soup

    return None

def extract_simple_tokens(name):
    tokens = re.findall(r"[A-Za-z]{4,}", name.lower())
    return {tok for tok in tokens if tok not in {"inc", "llc", "company", "corp", "co", "group"}}

def extract_and_score_links(soup: BeautifulSoup, company_name: str):
    normalized = re.sub(r'[^a-z0-9]', '', company_name.lower())
    keywords = extract_simple_tokens(company_name)
    candidates: list[tuple[int, str]] = []

    deep = soup.select_one(".b_entityTP a[href]")
    if deep:
        href = deep["href"]
        if not any(skip in href for skip in SKIP_DOMAINS):
            root = get_root_homepage(href)
            return [(10_000, root)]

    print("\n🔍 Printing all Bing blocks:")
    for block in soup.select("li.b_algo"):
        a = block.select_one("h2 a")
        if not a or not a.get("href"):
            continue

        href = a["href"]
        title = a.get_text(strip=True)
        p_tag = block.select_one(".b_caption p")
        snippet = p_tag.get_text(strip=True) if p_tag else ""

        if any(domain in href.lower() for domain in SKIP_DOMAINS):
            continue
        if urlparse(href).path.lower().endswith(".pdf"):
            continue

        parsed = urlparse(href)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        score = 0
        low_href = href.lower()
        low_title = title.lower()
        low_snip = snippet.lower()

        if normalized in domain:
            score += 100
        elif any(tok in domain for tok in keywords):
            score += 50

        if path in ("", "/", "/home"):
            score += 10
        elif any(p in path for p in ["about", "company", "overview", "contact"]):
            score += 30

        if any(term in low_snip for term in BIOTECH_TERMS):
            score += 15

        score -= len(domain) // 3

        if any(x in href for x in ["ir.", "finance.", "seekingalpha"]):
            score -= 5

        candidates.append((score, href))
        print(f"    → Candidate scored {score}: {href}")

    if not candidates:
        print("    ❌ extract_and_score_links: no good candidates found")
        print("    ⚠️ Trying guessed domain fallback...")
        fallback: list[tuple[int, str]] = []
        for d in guess_possible_domains(company_name):
            url = f"https://{d.strip()}"
            if try_url_with_playwright_fallback(url, company_name):
                root = get_root_homepage(url)
                fallback.append((0, root))
                print(f"    ✅ fallback domain valid: {root}")
        return fallback

    return sorted(candidates, key=lambda x: x[0], reverse=True)

def get_root_homepage(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, "", "", "", ""))

def verify_website_fast(url: str, company_name: str, tried_www: bool = False) -> bool:
    print(f"  🔍 verify_website_fast: GET {url}")
    content = safe_get_html(url)

    if not content and not tried_www:
        parsed = urlparse(url)
        alt_url = urlunparse(parsed._replace(netloc="www." + parsed.netloc))
        print(f"    ❌ retrying with www: {alt_url}")
        content = safe_get_html(alt_url)

    if not content:
        return False

    content = content.lower()
    for tok in extract_simple_tokens(company_name):
        if tok in content:
            print(f"    ✅ token match: '{tok}'")
            return True

    print("    ❌ no tokens found")
    return False