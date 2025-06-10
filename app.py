import io
import time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from clean_company_data import preprocess_df
from scraper.company_processor import process_company
import psutil

st.set_page_config(page_title="Company Ranking Tool", layout="wide")
st.title("📊 Company Ranking Dashboard")
st.write(f"🔍 Memory usage: {psutil.Process().memory_info().rss / 1024 ** 2:.2f} MB")


# --- Phase 1: Upload CSV ---
with st.container():
    st.markdown("### 📤 Upload Zoho Accounts CSV")
    uploaded_file = st.file_uploader(
        label="To export: Zoho > Accounts > Actions > Export Accounts. It should be in CSV format, as it is upon Zoho export, but also accepts Excel files.",
        type=["csv", "xlsx"],
        help="To export: Zoho > Accounts > Actions > Export Accounts. You only need to include 'Account Name'; other fields like 'Website', 'Region', 'Funding Stage', 'Employees', and 'Major Segment' are optional."
    )
    st.caption("💡 Tip: Only the 'Account Name' field is required. You can customize fields in your export as you wish.")

df: pd.DataFrame = None
augmented_df = None
ranked_df = None

if uploaded_file:
    if uploaded_file.name.endswith(".xlsx"):
        df = preprocess_df(pd.read_excel(uploaded_file))
    else:
        df = preprocess_df(pd.read_csv(uploaded_file))
    st.markdown("### 🔍 Uploaded Data")
    st.dataframe(df)


# Predeclare placeholders (above fold)
progress_bar = st.empty()
status = st.empty()

# --- Phase 2: Scrape Websites & Regions ---
if df is not None:
    # --- Preference Input ---
    st.markdown("### 🎯 Ranking Preferences")

    st.markdown("""
    **How Ranking Works:**  
    Each company is scored based on how well it matches your preferences and company attributes:
    
    - **Small company size** (fewer than 100 employees): +1 point  
    - **Matching target region** (if selected): +1 point  
    - **Funding stage is Seed or Series A**: +1 point  
    - **Matching major segment** (if selected): +1 point  
    
    The final score ranges from **0 to 4**, and companies are ranked from highest to lowest score.
    """)

    region_options = ["No preference"] + sorted(df["Region"].dropna().unique())
    segment_options = ["No preference"] + sorted(df["Major Segment"].dropna().unique())

    selected_region = st.selectbox("Target Region", options=region_options)
    selected_segment = st.selectbox("Target Major Segment", options=segment_options)

    st.caption("Tip: For best results, run this in **batches of 30 companies or fewer**. Scraping thousands at once may trigger delays or bot protections.")

    if st.button("🌐 Fill in Website + Region & Score Companies"):
        progress_bar = st.progress(0)
        status = st.empty()

        # --- Augmentation ---
        error_log = []

        def _process_row(row, idx):
            company = row["Account Name"]
            orig_url = row.get("Website") or None
            orig_region = row.get("Region") or None

            if orig_url and orig_region:
                return row

            try:
                info = process_company(
                    company,
                    scrape_website=not bool(orig_url),
                    scrape_location=not bool(orig_region),
                )
                return {
                    **row,
                    "Website": info.get("url") or orig_url,
                    "Region": info.get("region") or orig_region,
                }
            except Exception as e:
                error_log.append({
                    "Index": idx,
                    "Company": company,
                    "Error": str(e)
                })
                return {
                    **row,
                    "Website": orig_url,
                    "Region": orig_region
                }


        results = [None] * len(df)
        future_to_index = {}
        status.text("Taking a few minutes to fill in websites and regions...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            for idx, (_, row) in enumerate(df.iterrows()):
                future = executor.submit(_process_row, row, idx)
                future_to_index[future] = idx


        completed = 0
        for future in as_completed(future_to_index):
            i = future_to_index[future]
            try:
                results[i] = future.result()
            except Exception as e:
                row = df.iloc[i]
                results[i] = {**row, "Website": row.get("Website"), "Region": row.get("Region"), "Error": str(e)}

            completed += 1
            progress_bar.progress(completed / len(df))
            status.text(f"Processed {completed}/{len(df)} companies…")

        augmented_df = pd.DataFrame(results)
        status.success("✅ Augmentation complete.")

        if error_log:
            st.warning(f"{len(error_log)} companies encountered errors during scraping.")
            with st.expander("See error log"):
                st.dataframe(pd.DataFrame(error_log))


        # --- Scoring ---
        def score_row(row):
            score = 0
            try:
                if int(row.get("Employees", 0)) < 100:
                    score += 1
            except:
                pass
            if selected_region != "No preference" and row.get("Region") == selected_region:
                score += 1
            if row.get("Funding Stage") in ["Seed", "Series A"]:
                score += 1
            if selected_segment != "No preference" and row.get("Major Segment") == selected_segment:
                score += 1
            return score

        ranked_df = augmented_df.copy()
        ranked_df["Rank"] = ranked_df.apply(score_row, axis=1)
        ranked_df = ranked_df.sort_values(by="Rank", ascending=False)

        st.markdown("### 🏆 Ranked Companies")
        st.dataframe(ranked_df)

        # Save to session state for export
        st.session_state["ranked_df"] = ranked_df

# --- Phase 3: Export & Summary ---
if augmented_df is not None:
    with st.container():
        # Show which companies were augmented
        st.markdown("### 🛠️ Updated Companies & Fields")
        st.caption(
            "This table shows companies whose **website** or **region** fields were updated via web scraping. "
            "Use it to double-check for any inaccurate or unexpected data changes before exporting."
        )
        augmented_only = []
        for i, row in augmented_df.iterrows():
            orig_row = df.iloc[i]
            updated_website = row.get("Website") != orig_row.get("Website")
            updated_region = row.get("Region") != orig_row.get("Region")
            if updated_website or updated_region:
                augmented_only.append({
                    "Company": row.get("Account Name"),
                    "Updated Website": row.get("Website"),
                    "Updated Region": row.get("Region")
                })

        if augmented_only:
            st.dataframe(pd.DataFrame(augmented_only))
        else:
            st.success("No companies needed augmentation.")
        
        st.markdown("### 💾 Export Results")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            augmented_df.to_excel(writer, index=False, sheet_name="Companies")
        buffer.seek(0)

        st.download_button(
            label="⬇️ Export Zoho Accounts Excel File",
            data=buffer,
            file_name="companies_with_websites_and_regions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )