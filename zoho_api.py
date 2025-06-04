import requests
import streamlit as st

def get_access_token():
    url = "https://accounts.zoho.com/oauth/v2/token"
    params = {
        "refresh_token": st.secrets["zoho"]["refresh_token"],
        "client_id": st.secrets["zoho"]["client_id"],
        "client_secret": st.secrets["zoho"]["client_secret"],
        "grant_type": "refresh_token"
    }
    res = requests.post(url, params=params)
    return res.json().get("access_token")

def fetch_leads():
    token = get_access_token()
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    res = requests.get("https://www.zohoapis.com/crm/v2/Leads", headers=headers)
    leads = res.json().get("data", [])
    return pd.DataFrame(leads)
