import io
import pandas as pd
import streamlit as st
from utils.scoring import score_row

def run_rank_only_tab():
    static_file = st.file_uploader("Upload Pre-Filled Data", type=["csv", "xlsx"], key="rank_only_uploader")
    if static_file:
        df = pd.read_excel(static_file) if static_file.name.endswith(".xlsx") else pd.read_csv(static_file)
        st.dataframe(df)

        region_options = ["No preference"] + sorted(df["Region"].dropna().unique())
        segment_options = ["No preference"] + sorted(df["Major Segment"].dropna().unique())

        selected_region = st.selectbox("Target Region", region_options, key="rank_only_region")
        selected_segment = st.selectbox("Target Major Segment", segment_options, key="rank_only_segment")

        df["Rank"] = df.apply(lambda r: score_row(r, selected_region, selected_segment), axis=1)
        df = df.sort_values("Rank", ascending=False)
        st.dataframe(df)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        st.download_button("⬇️ Download", buffer.getvalue(), "ranked_only_companies.xlsx")

