import io
import pandas as pd
import streamlit as st
from utils.scoring import score_row

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

        selected_region = st.selectbox("Target Region", region_options, key="rank_only_region")
        selected_segment = st.selectbox("Target Major Segment", segment_options, key="rank_only_segment")

        df["Rank"] = df.apply(lambda r: score_row(r, selected_region, selected_segment), axis=1)
        df = df.sort_values("Rank", ascending=False)

        st.markdown("### 🏆 Ranked Companies")
        st.dataframe(df)

        st.markdown("### 💾 Export Results")
        buffer = io.BytesIO()
        export_df = df.drop(columns=["Rank"])
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False)
        st.download_button("⬇️ Download", buffer.getvalue(), "ranked_only_companies.xlsx")
