# main.py

import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from company_processor import process_company
from employee_scraper import MultiSourceEmployeeScraper

if __name__ == "__main__":
    companies = [
        {"company": "Glycostem"},
    ]

    location_results = []
    size_results = []
    size_scraper = MultiSourceEmployeeScraper()

    # 1) Scrape location in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_company, row["company"]): row for row in companies}
        for future in as_completed(futures):
            row = futures[future]
            try:
                loc = future.result()
            except Exception:
                loc = {
                    "company": row["company"],
                    "url": None,
                    "country": None,
                    "state": None,
                    "region": None
                }
            location_results.append(loc)

    # 2) Lookup size sequentially
    for loc in location_results:
        comp = loc["company"]
        print(f"\n=== Looking up size for '{comp}' ===")
        size_count = size_scraper.get_employee_count(comp)
        size_results.append({
            "company": comp,
            "size": size_count if size_count is not None else "Not Found"
        })
        time.sleep(2)  # rate‐limit

    # 3) Merge into DataFrame
    df_locs = pd.DataFrame(location_results)
    df_sizes = pd.DataFrame(size_results)
    df = df_locs.merge(df_sizes, on="company", how="left")

    print("\nFinal Results:\n", df)
    # df.to_csv("company_regions_and_sizes.csv", index=False)
