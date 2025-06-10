import io
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from clean_company_data import preprocess_df
from scraper.company_processor import process_company

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
        company     = row["Account Name"]
        orig_url    = row.get("Website") or None
        orig_region = row.get("Region")  or None

        if orig_url and orig_region:
            return row

        # Otherwise, hit your single pipeline:
        info = process_company(
            company,
            scrape_website = not bool(orig_url),
            scrape_location = not bool(orig_region),
        )
        return {
            **row,
            "Website": info.get("url") or orig_url,
            "Region":  info.get("region") or orig_region,
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
