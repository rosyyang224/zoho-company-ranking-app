# enrich_website_scraper.py

import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from config import SUPABASE_DB_URL

engine = create_engine(SUPABASE_DB_URL)

# --- Basic Google Search Scraper ---
def google_search_company_website(company_name):
    try:
        query = quote_plus(company_name + " official site")
        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Google search result links are inside <a> tags with href starting with http
        for a in soup.select("a"):
            href = a.get("href")
            if href and href.startswith("http") and "google" not in href:
                return href.split("&")[0]  # Clean tracking

    except Exception as e:
        print(f"Error scraping {company_name}: {e}")

    return None

# --- Main Enrichment Script ---
def enrich_missing_websites():
    with engine.begin() as conn:
        result = conn.execute(text("SELECT id, name FROM companies WHERE website IS NULL OR website = ''"))
        companies = result.fetchall()

        print(f"Found {len(companies)} companies missing websites")

        for row in companies:
            company_id = row.id
            name = row.name
            website = google_search_company_website(name)

            if website:
                print(f"Updating {name} with website {website}")
                conn.execute(
                    text("UPDATE companies SET website = :website WHERE id = :id"),
                    {"website": website, "id": company_id}
                )
            else:
                print(f"No website found for {name}")

if __name__ == "__main__":
    enrich_missing_websites()
