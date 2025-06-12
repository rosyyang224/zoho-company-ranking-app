import pandas as pd
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from company_processor import (
    process_company,
    fetch_html_with_fallback,
    find_contact_link,
    fetch_page_with_playwright
)
from location_utils import parse_contact_page, assign_region
from bs4 import BeautifulSoup

def normalize_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "").strip().lower().rstrip("/")
    except Exception:
        return ""

def _process_website_row(row):
    company = row["Company"]
    known_website = row.get("Original Website", "").strip()
    result = {
        "Company": company,
        "Original Website": known_website,
        "Scraped Website": None,
        "Website Match": "❌"
    }

    if not company or not known_website:
        return result

    print(f"\n=== Processing (website): {company} ===")
    try:
        scraped = process_company(company)
        scraped_url = scraped.get("url") or ""
        known_dom = normalize_domain(known_website)
        scraped_dom = normalize_domain(scraped_url)

        match = "✅" if known_dom and known_dom == scraped_dom else "❌"
        print(f"    • Known:   {known_dom or '—'}")
        print(f"    • Scraped: {scraped_dom or '—'}")
        print(f"    • Match:   {match}")

        result.update({
            "Scraped Website": scraped_url,
            "Website Match": match
        })
    except Exception as e:
        print(f"❌ Failed for {company}: {e}")

    return result

def test_websites(csv_path="top_cgt_companies.csv", max_workers=5):
    df = pd.read_csv(csv_path)
    headers = set(df.columns.astype(str))
    df = df[~df['Company'].isin(headers)]
    rows = df.to_dict(orient="records")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_row = {executor.submit(_process_website_row, row): row for row in rows}
        for future in as_completed(future_to_row):
            res = future.result()
            results.append(res)

    pd.DataFrame(results).to_csv("cgt_scraper_test_results.csv", index=False)
    print("\n✅ Website scraping test complete. Results saved to cgt_scraper_test_results.csv")

def _process_location_row(row):
    company = row["Company"]
    known_url = row.get("Original Website", "").strip()
    expected = row.get("Region", "").strip()
    result = {
        "Company": company,
        "Provided Website": known_url,
        "Country": "Not Found",
        "State": "Not Found",
        "Region": None,
        "Location Match": "❌"
    }

    if not company or not known_url:
        return result

    if not known_url.lower().startswith("http"):
        known_url = "https://" + known_url

    print(f"\n=== Processing (location): {company} ===")
    print(f"  🌐 Using provided website: {known_url}")

    try:
        homepage_html, soup_home = fetch_html_with_fallback(known_url)
        contact_link = find_contact_link(soup_home, known_url)
        if contact_link:
            print(f"  📞 Found contact page: {contact_link}")
            html_content, soup_to_parse = fetch_html_with_fallback(contact_link)
        else:
            print("  🏠 Using homepage for location scan")
            html_content, soup_to_parse = homepage_html, soup_home

        body_lines = [ln.strip() for ln in soup_to_parse.get_text(separator="\n").split("\n") if ln.strip()]
        country, state = parse_contact_page(soup_to_parse, html_content, body_lines)

        if not country and contact_link:
            print("  🧭 Retrying with Playwright…")
            rendered = fetch_page_with_playwright(contact_link)
            soup_r = BeautifulSoup(rendered, "html.parser")
            lines_r = [ln.strip() for ln in soup_r.get_text(separator="\n").split("\n") if ln.strip()]
            country, state = parse_contact_page(soup_r, rendered, lines_r)
            if country:
                print(f"  🎉 Playwright parsed: country={country}, state={state}")

        region = assign_region(country, state)
        match = "✅ Match" if (region or "").lower() == expected.lower() else "❌ Mismatch"

        print(f"  Final → country={country}, state={state}, region={region}")
        print(f"     Match: {match}")

        result.update({
            "Country": country or "Not Found",
            "State": state or "Not Found",
            "Region": region,
            "Location Match": match
        })
    except Exception as e:
        print(f"❌ Failed for {company}: {e}")

    return result

def test_location(csv_path="top_cgt_companies.csv", max_workers=5):
    df = pd.read_csv(csv_path)
    headers = set(df.columns.astype(str))
    df = df[~df['Company'].isin(headers)]
    rows = df.to_dict(orient="records")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_row = {executor.submit(_process_location_row, row): row for row in rows}
        for future in as_completed(future_to_row):
            res = future.result()
            results.append(res)

    pd.DataFrame(results).to_csv("output/cgt_location_scraping_results.csv", index=False)
    print("\n✅ Location-only test complete. Results saved to cgt_location_scraping_results.csv")

if __name__ == "__main__":
    # For website tests:
    test_websites(max_workers=8)

    # For location tests:
    # test_location(max_workers=8)
