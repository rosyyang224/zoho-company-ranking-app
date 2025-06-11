import io
import pandas as pd
import streamlit as st
from utils.scoring import score_row, compute_score, show_ranking_config

def run_rank_only_tab():
    st.markdown("### Upload Pre-Filled Zoho Accounts Data")
    static_file = st.file_uploader(
        label="To export: Zoho > Accounts > Actions > Export Accounts. It should be in CSV format, as it is upon Zoho export, but also accepts Excel files.",
        help="This option assumes all data is pre-filled — no web scraping will occur.",
        key="rank_only_uploader"
    )
    st.caption("💡 Tip: This mode is faster. You can upload large files because there's no scraping.")

    if static_file:
        df = pd.read_excel(static_file) if static_file.name.endswith(".xlsx") else pd.read_csv(static_file)
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
            ranking_config = show_ranking_config(df, key_prefix="rank")

        df["Rank"] = df.apply(lambda r: compute_score(r, ranking_config), axis=1)
        df = df.sort_values("Rank", ascending=False)

        st.markdown("### 🏆 Ranked Companies")
        st.dataframe(df)

        st.markdown("### 💾 Export Results")
        st.caption("The exported file does not include the 'Ranking' column so that you can easily re-import back to Zoho, since Zoho fields don't have a 'Ranking' column")
        export_df = df.drop(columns=[c for c in ["Rank", "Error"] if c in df.columns])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False)
        st.download_button("⬇️ Download", buffer.getvalue(), "ranked_only_companies.xlsx")