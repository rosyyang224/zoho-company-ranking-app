import streamlit as st
import pandas as pd
from run_pipeline import run_pipeline

st.set_page_config(page_title="Company Ranking Tool", layout="wide")
st.title("Company Ranking Dashboard")

# Button to run full pipeline
if st.button("Run Company Pipeline"):
    with st.spinner("Processing company data..."):
        run_pipeline()
    st.success("Pipeline complete! Company data processed.")

# Load and display output if available
try:
    df = pd.read_csv("output/Cleaned_Company_Table.csv")
    st.markdown("### Cleaned Company Summary")
    st.dataframe(df)
except FileNotFoundError:
    st.warning("No processed company file found. Please click 'Run Company Pipeline' to generate one.")
