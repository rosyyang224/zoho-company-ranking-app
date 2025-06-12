import pandas as pd
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import argparse
import os

from scraper.company_processor import process_company

def normalize_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "").strip().lower().rstrip("/")
    except Exception:
        return ""

def process_test_row(row):
    company = row["Company"]
    expected_website = row.get("Website", "").strip()
    expected_region = row.get("Region", "").strip()

    result = {
        "Company": company,
        "Expected Website": expected_website,
        "Scraped Website": None,
        "Website Match": "❌",
        "Expected Region": expected_region,
        "Scraped Region": None,
        "Region Match": "❌",
    }

    if not company:
        return result

    print(f"\n=== Processing: {company} ===")
    try:
        scraped = process_company(company)
        scraped_url = scraped.get("url") or ""
        scraped_region = scraped.get("region") or ""

        # Website comparison
        known_dom = normalize_domain(expected_website)
        scraped_dom = normalize_domain(scraped_url)
        website_match = known_dom and scraped_dom and known_dom == scraped_dom

        print(f"  🌐 Expected: {known_dom or '—'}")
        print(f"  🌐 Scraped:  {scraped_dom or '—'}")
        print(f"  ✅ Website Match: {'✅' if website_match else '❌'}")

        result["Scraped Website"] = scraped_url
        result["Website Match"] = "✅" if website_match else "❌"

        # Region comparison
        print(f"  🌍 Expected Region: {expected_region or '—'}")
        print(f"  🌍 Scraped Region:  {scraped_region or '—'}")
        result["Scraped Region"] = scraped_region

        if expected_region and scraped_region.lower() == expected_region.lower():
            result["Region Match"] = "✅"
            print("  ✅ Region Match")
        else:
            print("  ❌ Region Mismatch")

    except Exception as e:
        print(f"  ❌ Error processing {company}: {e}")

    return result

def run_tests_from_csv(path):
    df = pd.read_csv(path)
    results = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_test_row, row) for _, row in df.iterrows()]
        for future in as_completed(futures):
            results.append(future.result())

    out_df = pd.DataFrame(results)
    out_path = os.path.splitext(path)[0] + "_results.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\n✅ Results written to {out_path}")

if __name__ == "__main__":
    run_tests_from_csv("data/top_cgt_companies.csv")
