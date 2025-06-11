import io, time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.clean_company_data import preprocess_df
from scraper.company_processor import process_company
from utils.scoring import score_row, compute_score, show_ranking_config

def run_scrape_and_rank_tab():
    st.markdown("### Upload Zoho Accounts Data")
    uploaded_file = st.file_uploader(
        label="To export: Zoho > Accounts > Actions > Export Accounts. It should be in CSV format, as it is upon Zoho export, but also accepts Excel files.",
        type=["csv", "xlsx"],
        help="To export: Zoho > Accounts > Actions > Export Accounts. You only need to include 'Account Name'; other fields like 'Website', 'Region', 'Funding Stage', 'Employees', and 'Major Segment' are optional.",
        key="file_uploader"  # Add a key to prevent reprocessing
    )
    st.caption("💡 Tip: This mode is slower. Keep batches in <30 companies to avoid bot detection and delays.")

    # Only process new file if it's different from the stored one
    if uploaded_file:
        # Check if this is a new file
        if ("uploaded_file_name" not in st.session_state or 
            st.session_state.uploaded_file_name != uploaded_file.name or
            "df" not in st.session_state):
            
            st.session_state.uploaded_file = uploaded_file
            st.session_state.uploaded_file_name = uploaded_file.name
            st.session_state.df = preprocess_df(uploaded_file)
            st.session_state.show_results = False
            # Clear previous results when new file is uploaded
            if "augmented_df" in st.session_state:
                del st.session_state.augmented_df
            if "ranked_df" in st.session_state:
                del st.session_state.ranked_df

    if st.session_state.get("df") is not None:
        df = st.session_state.df
        st.markdown("### 🔍 Uploaded Data")
        st.dataframe(df)

        st.markdown("### 🎯 Ranking Preferences")
        st.markdown("By default, companies are ranked using a **Point-Based System** with only employees < 100 having points.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            #### Point-Based Scoring (Default)
            Each selected preference adds **+1 point** to a company’s score:
            - Employees fewer than threshold (default: 100)  
            - Region matches your selection (optional)  
            - Major segment matches your selection (optional)  
            - Funding stage matches your selection (optional)  

            Companies with more matches score higher and are ranked at the top.
            """)

        with col2:
            st.markdown("""
            #### Weighted Scoring (Optional)
            Switch to **Weighted Mode** to assign custom importance to each criterion.
            - For example: Region weight = 2.0, Funding stage = 0.5  
            - Companies are scored based on how well they match, *scaled* by your weights  

            This is helpful if some factors matter more than others in your decision-making.
            """)

        st.markdown("> 📝 Tip: Leaving a field as **'No preference'** means it won’t affect the ranking.")

        with st.expander("⚙️ Customize Ranking System"):
            st.session_state.ranking_config = show_ranking_config(df, key_prefix="scrape")
        
        # Only show the button if we don't have results yet
        if not st.session_state.get("show_results", False):
            if st.button("🌐 Fill in Website + Region & Score Companies", key="process_button"):
                start = time.time()
                status = st.empty()
                bar = st.progress(0)
                results, error_log = [], []

                def _process(row, i):
                    try:
                        company = row["Account Name"]
                        url, region = row.get("Website"), row.get("Region")
                        row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                        
                        if url and region:
                            return row_dict
                        
                        info = process_company(company, scrape_website=not url, scrape_location=not region)
                        return {**row_dict, "Website": info.get("url", url), "Region": info.get("region", region)}
                    except Exception as e:
                        error_log.append({"Index": i, "Company": row["Account Name"], "Error": str(e)})
                        row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                        return row_dict

                with ThreadPoolExecutor(max_workers=5) as ex:
                    futures = {ex.submit(_process, r, i): i for i, (_, r) in enumerate(df.iterrows())}
                    results = [None] * len(df)
                    for count, fut in enumerate(as_completed(futures)):
                        i = futures[fut]
                        results[i] = fut.result()
                        bar.progress((count + 1) / len(df))
                        status.text(f"Processed {count + 1}/{len(df)}")

                augmented_df = pd.DataFrame(results)
                ranked = augmented_df.copy()
                ranked["Rank"] = ranked.apply(lambda r: compute_score(r, st.session_state.ranking_config), axis=1)
                ranked = ranked.sort_values("Rank", ascending=False)

                st.session_state.augmented_df = augmented_df
                st.session_state.ranked_df = ranked
                st.session_state.show_results = True
                status.success("✅ Augmentation complete.")
                st.caption(f"⏱️ Time: {int(time.time() - start)}s")
                st.rerun() 
        else:
            # Show a button to reset and reprocess
            if st.button("🔄 Reset and Reprocess", key="reset_button"):
                st.session_state.show_results = False
                if "augmented_df" in st.session_state:
                    del st.session_state.augmented_df
                if "ranked_df" in st.session_state:
                    del st.session_state.ranked_df
                st.rerun()

    # Display results if they exist
    if st.session_state.get("show_results") and st.session_state.get("ranked_df") is not None:
        st.markdown("### 🏆 Ranked Companies")
        st.dataframe(st.session_state.ranked_df)

        st.markdown("### 💾 Export")
        st.markdown("The exported file does not include the 'Ranking' column so that you can easily re-import back to Zoho, since Zoho fields currently lack a ranking column")

        export_df = st.session_state.ranked_df.drop(columns=[c for c in ["Rank", "Error"] if c in st.session_state.ranked_df.columns])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False)
        st.download_button(
            "⬇️ Download", 
            buffer.getvalue(), 
            "ranked_companies.xlsx",
            key="download_button"
        )