import io
import time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from clean_company_data import preprocess_df
from scraper.company_processor import process_company

st.set_page_config(page_title="Company Ranking Tool", layout="wide")
st.title("📊 Company Ranking Dashboard")

# --- Phase 1: Upload CSV ---
with st.container():
    uploaded_file = st.file_uploader(
        "Upload your Zoho accounts CSV below",
        type=["csv"],
        help="Should have at least a 'Company' column and optionally 'Website', 'Region', 'Funding Stage', '# Employees', and 'Major Segment'."
    )

df: pd.DataFrame = None
augmented_df = None
ranked_df = None

if uploaded_file:
    df = preprocess_df(uploaded_file)
    st.markdown("### 🔍 Uploaded Data")
    st.dataframe(df)

# Predeclare placeholders (above fold)
progress_bar = st.empty()
status = st.empty()

# --- Phase 2: Scrape Websites & Regions ---
if df is not None:
    # --- Preference Input ---
    st.markdown("### 🎯 Ranking Preferences")
    region_options = ["No preference"] + sorted(df["Region"].dropna().unique())
    segment_options = ["No preference"] + sorted(df["Major Segment"].dropna().unique())

    selected_region = st.selectbox("Target Region", options=region_options)
    selected_segment = st.selectbox("Target Major Segment", options=segment_options)

    if st.button("🌐 Fill in Website + Region & Score Companies"):
        progress_bar = st.progress(0)
        status = st.empty()

        # --- Augmentation ---
        def _process_row(row):
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
                return {
                    **row,
                    "Website": orig_url,
                    "Region": orig_region,
                    "Error": str(e)
                }

        results = [None] * len(df)
        future_to_index = {}
        status.text("Taking a few minutes to fill in websites and regions...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            for idx, (_, row) in enumerate(df.iterrows()):
                future = executor.submit(_process_row, row)
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

        # --- Scoring ---
        def score_row(row):
            score = 0
            try:
                if int(row.get("# Employees", 0)) < 100:
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