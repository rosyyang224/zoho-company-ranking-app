import pandas as pd
from urllib.parse import urlparse
from company_processor import (
    process_company,
    fetch_html_with_fallback,
    find_contact_link,
    fetch_page_with_playwright
)
from bs4 import BeautifulSoup
from location_utils import parse_contact_page, assign_region


def normalize_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "").strip().lower().rstrip("/")
    except Exception:
        return ""


def test_websites(csv_path="top_cgt_companies.csv"):
    df = pd.read_csv(csv_path)
    # Drop any spurious header-like rows where Company matches column names
    header_names = set(df.columns.astype(str))
    df = df[~df['Company'].isin(header_names)]

    results = []

    for _, row in df.iterrows():
        company = row["Company"]
        known_website = row.get("Original Website", "")

        # Skip rows with missing company or website
        if not isinstance(company, str) or not company.strip():
            continue
        if not isinstance(known_website, str) or not known_website.strip():
            continue

        print(f"\n=== Processing: {company} ===")
        try:
            scraped = process_company(company)
            scraped_url = scraped.get("url")

            known_domain = normalize_domain(known_website)
            scraped_domain = normalize_domain(scraped_url)
            match = "✅" if known_domain and known_domain == scraped_domain else "❌"

            print(f"    • Known:   {known_domain or '—'}")
            print(f"    • Scraped: {scraped_domain or '—'}")
            print(f"    • Match:   {match}")

            results.append({
                "Company": company,
                "Original Website": known_website,
                "Scraped Website": scraped_url,
                "Website Match": match
            })

        except Exception as e:
            print(f"❌ Failed for {company}: {e}")
            results.append({
                "Company": company,
                "Original Website": known_website,
                "Scraped Website": None,
                "Website Match": "❌"
            })

    pd.DataFrame(results).to_csv("cgt_scraper_test_results.csv", index=False)
    print("\n✅ Website scraping test complete. Results saved to cgt_scraper_test_results.csv")


def test_location(csv_path="top_cgt_companies.csv"):
    df = pd.read_csv(csv_path)
    header_names = set(df.columns.astype(str))
    df = df[~df['Company'].isin(header_names)]
    results = []

    for _, row in df.iterrows():
        company = row["Company"]
        known_url = row.get("Original Website", "")
        expected_region = row.get("Region", "").strip()

        if not isinstance(company, str) or not company.strip():
            continue
        if not isinstance(known_url, str) or not known_url.strip():
            continue

        if not known_url.lower().startswith("http"):
            known_url = "https://" + known_url

        print(f"\n=== Processing: {company} ===")
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

            # Determine match
            match = (
                "✅ Match"
                if (region or "").strip().lower() == expected_region.lower()
                else "❌ Mismatch"
            )

            print(f"  Final → country={country}, state={state}, region={region}")
            print(f"     Match: {match}")

            results.append({
                "Company": company,
                "Provided Website": known_url,
                "Country": country or "Not Found",
                "State": state or "Not Found",
                "Region": region,
                "Location Match": match
            })

        except Exception as e:
            print(f"Failed to process {company}: {e}")
            results.append({
                "Company": company,
                "Provided Website": known_url,
                "Country": "Error",
                "State": "Error",
                "Region": "Error",
                "Location Match": "❌ Error"
            })

    pd.DataFrame(results).to_csv("cgt_location_scraping_results.csv", index=False)
    print("\n✅ Location-only test complete. Results saved to cgt_location_scraping_results.csv")

if __name__ == "__main__":
    # test_websites()
    test_location()
