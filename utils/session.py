import streamlit as st

def initialize_session_state():
    for key in ["uploaded_file", "df", "augmented_df", "ranked_df"]:
        if key not in st.session_state:
            st.session_state[key] = None