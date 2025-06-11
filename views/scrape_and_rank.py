import io, time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.clean_company_data import preprocess_df
from scraper.company_processor import process_company
from utils.scoring import score_row

def run_scrape_and_rank_tab():
    uploaded_file = st.file_uploader("Upload Zoho CSV or Excel", type=["csv", "xlsx"], help="At minimum include 'Account Name'.", key="scrape_upload")
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        st.session_state.df = preprocess_df(uploaded_file)

    if st.session_state.df is not None:
        df = st.session_state.df
        st.dataframe(df)

        region_options = ["No preference"] + sorted(df["Region"].dropna().unique())
        segment_options = ["No preference"] + sorted(df["Major Segment"].dropna().unique())

        selected_region = st.selectbox("Target Region", region_options)
        selected_segment = st.selectbox("Target Major Segment", segment_options)

        if st.button("🌐 Fill in Website + Region & Score Companies"):
            start = time.time()
            status = st.empty()
            bar = st.progress(0)
            results, error_log = [], []

            def _process(row, i):
                try:
                    company = row["Account Name"]
                    url, region = row.get("Website"), row.get("Region")
                    if url and region:
                        return row
                    info = process_company(company, scrape_website=not url, scrape_location=not region)
                    return {**row, "Website": info.get("url", url), "Region": info.get("region", region)}
                except Exception as e:
                    error_log.append({"Index": i, "Company": row["Account Name"], "Error": str(e)})
                    return {**row}

            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = {ex.submit(_process, r, i): i for i, (_, r) in enumerate(df.iterrows())}
                results = [None] * len(df)
                for count, fut in enumerate(as_completed(futures)):
                    i = futures[fut]
                    results[i] = fut.result()
                    bar.progress((count + 1) / len(df))
                    status.text(f"Processed {count + 1}/{len(df)}")

            st.session_state.augmented_df = pd.DataFrame(results)
            status.success("✅ Augmentation complete.")
            st.caption(f"⏱️ Time: {int(time.time() - start)}s")

            ranked = st.session_state.augmented_df.copy()
            ranked["Rank"] = ranked.apply(lambda r: score_row(r, selected_region, selected_segment), axis=1)
            ranked = ranked.sort_values("Rank", ascending=False)
            st.session_state.ranked_df = ranked

            st.dataframe(ranked)

            st.markdown("### 💾 Export")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                ranked.to_excel(writer, index=False)
            st.download_button("⬇️ Download", buffer.getvalue(), "ranked_companies.xlsx")