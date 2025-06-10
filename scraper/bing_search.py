import re
import time
import requests
from requests.exceptions import SSLError
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup

from scraper.scraper_config import FAKE_CHROME_HEADERS, SKIP_DOMAINS, BIOTECH_TERMS, ACQUISITION_KEYWORDS

session = requests.Session()
session.headers.update(FAKE_CHROME_HEADERS)


def guess_possible_domains(name):
    name_lower = name.lower()
    base = re.sub(r'\W+', '', name_lower)
    guesses = [f"{base}.com"]

    if "therapeutics" in name_lower:
        prefix = re.sub(r"[ -]?therapeutics", "", name_lower)
        if prefix != name_lower:
            guesses += [
                f"{prefix}tx.com",
                f"{prefix}-tx.com",
                f"{prefix}.com",
                f"{prefix}therapeutics.com",
            ]

    if "biosciences" in name_lower or "biotech" in name_lower or "biotherapeutics" in name_lower:
        prefix = re.sub(r"[ -]?(biosciences|biotech)", "", name_lower)
        guesses += [
            f"{prefix}bio.com",
            f"{prefix}-bio.com",
            f"{prefix}.com"
        ]

    # Add fallback with dash manually if prefix extraction didn't catch it
    tokens = name_lower.split()
    if "therapeutics" in tokens:
        dash_prefix = "-".join(t for t in tokens if t != "therapeutics")
        guesses += [f"{dash_prefix}-tx.com"]
        guesses += [f"{dash_prefix}tx.com"]

    return list(dict.fromkeys(guesses))  # Deduplicate

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

    # 1. Directly try guessed domains via requests.get()
    print("  🔍 Trying direct domain guesses...")
    for domain in domains:
        test_url = f"https://{domain}"
        try:
            r = requests.get(test_url, timeout=5)
            if r.ok:
                print(f"  ✅ Direct domain valid: {test_url}")
                # Return a fake soup so we can pass the URL downstream
                return BeautifulSoup(f'<a href="{test_url}">{test_url}</a>', "html.parser")
            else:
                print(f"  ❌ Bad status: {r.status_code} for {test_url}")
        except Exception as e:
            print(f"  ❌ Failed to fetch {test_url}: {e}")

    # 2. Forced Bing queries (site:domain)
    for domain in domains:
        query = f"{company_name} site:{domain}"
        print(f"  🔍 Trying forced Bing query: '{query}'")
        soup = fetch_bing_results(query)
        if soup and soup.select_one("li.b_algo"):
            print(f"  ✅ Bing result found for forced query: {domain}")
            return soup

    # 3. Generic Bing query
    print(f"  🔍 Trying generic Bing search: '{company_name}'")
    soup = fetch_bing_results(company_name)

    # Reject soup if all links are from SKIP_DOMAINS
    if soup:
        result_blocks = soup.select("li.b_algo")
        if result_blocks:
            domains_seen = [
                urlparse(a.get("href", "")).netloc.lower()
                for a in soup.select("li.b_algo h2 a") if a and a.get("href")
            ]
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
    """
    Return a list of (score, candidate_url) tuples from Bing results,
    falling back to guessed domains if necessary.
    """
    normalized = re.sub(r'[^a-z0-9]', '', company_name.lower())
    keywords   = extract_simple_tokens(company_name)
    candidates: list[tuple[int, str]] = []

    # --- 1) Check Bing entity panel (high-confidence) ---
    deep = soup.select_one(".b_entityTP a[href]")
    if deep:
        href = deep["href"]
        if not any(skip in href for skip in SKIP_DOMAINS):
            root = get_root_homepage(href)
            # give it a super-high score so it sorts first
            return [(10_000, root)]

    # --- 2) Score the standard Bing blocks ---
    print("\n🔍 Printing all Bing blocks:")
    for block in soup.select("li.b_algo"):
        a = block.select_one("h2 a")
        if not a or not a.get("href"):
            continue

        href    = a["href"]
        title   = a.get_text(strip=True)
        p_tag = block.select_one(".b_caption p")
        snippet = p_tag.get_text(strip=True) if p_tag else ""

        if any(domain in href.lower() for domain in SKIP_DOMAINS):
            continue
        if urlparse(href).path.lower().endswith(".pdf"):
            continue

        score = 0
        low_href  = href.lower()
        low_title = title.lower()
        low_snip  = snippet.lower()

        # match your keywords or biotech terms
        for kw in keywords | BIOTECH_TERMS:
            if kw in low_href or kw in low_title or kw in low_snip:
                score += 1

        # bonus if the normalized company name is in the domain
        if normalized in urlparse(href).netloc:
            score += 100

        # bonus for root path
        if urlparse(href).path in ("", "/"):
            score += 10

        # penalize long domains or IR/finance subdomains
        score -= len(urlparse(href).netloc)
        if any(x in href for x in ["ir.", "finance.", "seekingalpha"]):
            score -= 5

        candidates.append((score, href))
        print(f"    → Candidate scored {score}: {href}")

    # --- 3) If still empty, try guessed domains ---
    if not candidates:
        print("    ❌ extract_and_score_links: no good candidates found")
        print("    ⚠️ Trying guessed domain fallback...")

        fallback: list[tuple[int,str]] = []
        for d in guess_possible_domains(company_name):
            dom = d.strip().replace(" ", "")
            test_url = f"https://{dom}"
            try:
                r = requests.get(test_url, timeout=5)
                if r.ok:
                    root = get_root_homepage(test_url)
                    fallback.append((0, root))
                    print(f"    ✅ fallback domain valid: {root}")
                else:
                    print(f"    ❌ fallback domain bad status: {r.status_code}")
            except Exception as e:
                print(f"    ❌ failed to reach {test_url}: {e}")

        return fallback  # may be empty, but at least it's a list

    # --- 4) Sort and return a list of (score, href) ---
    sorted_pairs = sorted(candidates, key=lambda x: x[0], reverse=True)
    return sorted_pairs

def get_root_homepage(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, "", "", "", ""))


def verify_website_fast(url: str, company_name: str, tried_www: bool = False) -> bool:
    """
    Returns True if the page at `url` looks like it belongs to `company_name`
    (by finding one of the extracted tokens in its HTML), False otherwise.
    On SSL errors it will retry once with 'www.' prefixed to the host.
    """
    try:
        print(f"  🔍 verify_website_fast: GET {url}")
        # leave verify=True so we catch real cert errors
        r = session.get(url, timeout=5)
        r.raise_for_status()
        content = r.text.lower()

    except SSLError as e:
        # retry once with www.<host>
        if not tried_www:
            parsed = urlparse(url)
            host = parsed.netloc
            alt_host = "www." + host
            alt_url = urlunparse(parsed._replace(netloc=alt_host))
            print(f"    ❌ SSL error; retrying with {alt_url}")
            return verify_website_fast(alt_url, company_name, tried_www=True)
        print(f"    ❌ SSL error even after www retry: {e}")
        return False

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            # your existing Playwright fallback
            print("    🚫 403 detected; using Playwright…")
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers(FAKE_CHROME_HEADERS)
                page.goto(url, timeout=15_000)
                page.wait_for_timeout(2000)
                content = page.content().lower()
                browser.close()
        else:
            print(f"    ❌ verify error: {e}")
            return False

    except Exception as e:
        print(f"    ❌ verify error: {e}")
        return False

    # now look for any token in the page text
    for tok in extract_simple_tokens(company_name):
        if tok in content:
            print(f"    ✅ verify: token '{tok}' found")
            return True

    print("    ❌ verify: no tokens found")
    return False