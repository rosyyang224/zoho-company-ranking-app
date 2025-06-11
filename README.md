# Zoho Company Ranking App

A lead-ranking platform for biopharma B2B targeting. This app combines data cleanup, enrichment, and customizable scoring to help prioritize outreach using information from Zoho CRM exports.

**Live App**: [zoho-company-ranking-app.streamlit.app](https://zoho-company-ranking-app.streamlit.app/)

---

## Features

- Customizable point-based or weighted ranking system
- Filter by region, size, funding stage, and modality
- Streamlit frontend for interactive filtering and exploration
- Backend pipeline for cleaning, enriching, and scoring Zoho CRM data
- Outputs a CSV ready for upload back into Zoho

---

## Running Locally

### 1. Clone the Repo & Set Up Environment
```bash
git clone https://github.com/rosyyang224/zoho-company-ranking-app.git 
cd zoho-company-ranking-app
```
Install Python dependencies:  
```bash
pip install -r requirements.txt
```

### 2. Run the Streamlit App  
```bash
streamlit run app.py
```  
This will launch the app at `http://localhost:8501/`.

---

## Pipeline Overview

The data pipeline processes Zoho lead or account exports, enriches them, and generates a cleaned CSV you can re-upload to Zoho.

### Workflow:
1. **Input**: Raw CSV from Zoho CRM (e.g. Leads or Accounts export)
2. **Processing**:
   - Cleans and normalizes company names, modalities, and sizes
   - Scrapes website and location data when missing
   - Applies fuzzy matching and scoring based on your filters
3. **Output**: A clean, ranked CSV saved in the `output/` directory

---

## Project Structure

- `app.py` – Main Streamlit frontend
- `scraper/` – Website and location scraping modules
- `utils/` – Helpers for data standardization and matching

### Development Notes

- No external API keys required
- All processing runs locally
- Output CSV is structured for quick re-import into Zoho
