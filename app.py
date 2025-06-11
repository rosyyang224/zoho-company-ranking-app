import streamlit as st
import psutil
from views.scrape_and_rank import run_scrape_and_rank_tab
from views.rank_only import run_rank_only_tab
from utils.session import initialize_session_state

st.set_page_config(page_title="Company Ranking Tool", layout="wide")
initialize_session_state()

st.title("📊 Company Ranking Dashboard")
st.write(f"🔍 Memory usage: {psutil.Process().memory_info().rss / 1024 ** 2:.2f} MB")

st.markdown("""
Run the 'Scrape & Rank' tab if you're looking to fill in data AND rank companies. Limit input to <30 companies at a time.  
Run the 'Rank Only' tab if you're looking to rerank all companies based on new criteria. No limit on input file size.
""")


tab1, tab2 = st.tabs(["🔎 Scrape & Rank", "📁 Rank Only"])

with tab1:
    run_scrape_and_rank_tab()

with tab2:
    run_rank_only_tab()