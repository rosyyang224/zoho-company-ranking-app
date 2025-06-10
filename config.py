import os
from dotenv import load_dotenv
import streamlit as st
from urllib.parse import quote_plus

# Load env vars (for local dev)
load_dotenv()

# Input/output paths
INPUT_DIR = "data"
OUTPUT_DIR = "output"
RAW_FILE = os.path.join(INPUT_DIR, "merged_accounts.csv")
CLEANED_FILE = os.path.join(OUTPUT_DIR, "Cleaned_Company_Table.csv")
SCRAPED_WEBSITES = os.path.join(OUTPUT_DIR, "company_website.csv")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"