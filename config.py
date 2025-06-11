import os
from dotenv import load_dotenv
import streamlit as st
from urllib.parse import quote_plus

# Load env vars (for local dev)
load_dotenv()

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"