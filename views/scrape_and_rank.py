import io, time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.clean_company_data import preprocess_df
from scraper.company_processor import process_company
from utils.scoring import score_row

def run_scrape_and_rank_tab():
    st.markdown("### Upload Zoho Accounts Data")
    uploaded_file = st.file_uploader(
        label="To export: Zoho > Accounts > Actions > Export Accounts. It should be in CSV format, as it is upon Zoho export, but also accepts Excel files.",
        type=["csv", "xlsx"],
        help="To export: Zoho > Accounts > Actions > Export Accounts. You only need to include 'Account Name'; other fields like 'Website', 'Region', 'Funding Stage', 'Employees', and 'Major Segment' are optional."
    )
    st.caption("💡 Tip: This mode is slower. Keep batches in <30 companies to avoid bot detection and delays.")
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        st.session_state.df = preprocess_df(uploaded_file)

    if st.session_state.df is not None:
        df = st.session_state.df
        st.dataframe(df)

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

        selected_region = st.selectbox("Target Region", region_options)
        selected_segment = st.selectbox("Target Major Segment", segment_options)

        if "show_results" not in st.session_state:
            st.session_state.show_results = False

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
            st.session_state.show_results = True

        if st.session_state.show_results and st.session_state.get("ranked_df") is not None:
            st.markdown("### 🏆 Ranked Companies")
            st.dataframe(st.session_state.ranked_df)

            st.markdown("### 💾 Export")
            export_df = st.session_state.ranked_df.drop(columns=[c for c in ["Rank", "Error"] if c in st.session_state.ranked_df.columns])
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False)
            st.download_button("⬇️ Download", buffer.getvalue(), "ranked_companies.xlsx")