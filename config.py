import os
from dotenv import load_dotenv
import streamlit as st
from urllib.parse import quote_plus

# Load env vars (for local dev)
load_dotenv()

# Database URL
user = st.secrets["database"]["user"]
pwd = st.secrets["database"]["password"]
host = st.secrets["database"]["host"]
dbname = st.secrets["database"]["dbname"]
encoded_pwd = quote_plus(pwd)
SUPABASE_DB_URL = f"postgresql://{user}:{encoded_pwd}@{host}:5432/{dbname}?sslmode=require"

# Input/output paths
INPUT_DIR = "data"
OUTPUT_DIR = "output"
RAW_FILE = os.path.join(INPUT_DIR, "Accounts_2025_06_04.csv")
CLEANED_FILE = os.path.join(OUTPUT_DIR, "Cleaned_Company_Table.csv")

# Optional: default CSV column names (if you want to standardize)
DEFAULT_COLUMNS = [
    "name", "website", "country", "state", "size", "funding_stage", "modality"
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"