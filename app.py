import io
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from clean_company_data import preprocess_df
from scraper.company_processor import process_company, fetch_html_with_fallback, find_contact_link, fetch_page_with_playwright
from scraper.location_utils import parse_contact_page, assign_region

st.set_page_config(page_title="Company Ranking Tool", layout="wide")
st.title("Company Ranking Dashboard")

# --- File uploader ---
uploaded_file = st.file_uploader(
    "Upload your Zoho accounts CSV",
    type=["csv"],
    help="Should have at least a 'Company' column and (optionally) 'Original Website' and 'Region'"
)

df: pd.DataFrame = None
if uploaded_file:
    df = preprocess_df(uploaded_file)
    st.markdown("### Uploaded Data")
    st.dataframe(df)

# container to hold augmented results
augmented_df = None

# --- Fill in website & region ---
if df is not None and st.button("Fill in website and region"):
    st.spinner("Scraping websites & locations…")
    results = []

    def _process_row(row):
        company       = row["Account Name"]
        orig_website  = (row.get("Website") or "").strip()
        orig_region   = (row.get("Region")  or "").strip()

        # Start by deciding what URL to use
        website = orig_website
        if not orig_website:
            # only scrape if the cell was blank
            scraped = process_company(company)
            website = scraped.get("url") or ""

        # Now only run location scraping if Region is blank *and* we have a website
        region = orig_region
        if not orig_region and website:
            try:
                home_html, home_soup = fetch_html_with_fallback(website)
                contact = find_contact_link(home_soup, website)
                if contact:
                    html, soup = fetch_html_with_fallback(contact)
                else:
                    html, soup = home_html, home_soup

                lines = [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]
                country, state = parse_contact_page(soup, html, lines)

                # fallback to Playwright if needed
                if not country and contact:
                    rendered = fetch_page_with_playwright(contact)
                    from bs4 import BeautifulSoup
                    soup2   = BeautifulSoup(rendered, "html.parser")
                    lines2  = [ln.strip() for ln in soup2.get_text("\n").split("\n") if ln.strip()]
                    country, state = parse_contact_page(soup2, rendered, lines2)

                region = assign_region(country, state) or ""

            except Exception:
                # leave region blank on error
                region = ""

        # Return all original columns + overwrite only the ones that needed filling
        return {
            **row,
            "Website": website,
            "Region":  region
        }


    # you can parallelize if you like
    with ThreadPoolExecutor(max_workers=5) as exec:
        futures = [exec.submit(_process_row, row) for _, row in df.iterrows()]
        for f in futures:
            results.append(f.result())

    augmented_df = pd.DataFrame(results)
    st.markdown("### Augmented Data")
    st.dataframe(augmented_df)

# --- Export button ---
if augmented_df is not None:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        augmented_df.to_excel(writer, index=False, sheet_name="Companies")
    buffer.seek(0)

    st.download_button(
        label="Export Zoho Accounts Excel File",
        data=buffer,
        file_name="companies_with_websites_and_regions.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
