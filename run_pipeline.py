import os
import pandas as pd
from sqlalchemy import create_engine, text
from clean_company_data import clean_company_table
from config import RAW_FILE, OUTPUT_DIR, CLEANED_FILE, SUPABASE_DB_URL, DEFAULT_COLUMNS

# -- DB INSERT --
def insert_companies_to_supabase(df, engine):
    with engine.begin() as conn:
        for _, row in df.iterrows():
            insert_sql = text("""
                INSERT INTO companies (name, website, country, state, size, funding_stage, modality)
                VALUES (:name, :website, :country, :state, :size, :funding_stage, :modality)
                ON CONFLICT (name) DO NOTHING
            """)
            conn.execute(insert_sql, {
                "name": row["name"],
                "website": row["website"],
                "country": row["country"],
                "state": row["state"],
                "size": row["size"],
                "funding_stage": row["funding_stage"],
                "modality": row["modality"]
            })

# -- MAIN PIPELINE --
def run_pipeline():
    print("Starting pipeline...")

    if not os.path.exists(RAW_FILE):
        print(f"Raw file not found: {RAW_FILE}")
        return

    df_raw = pd.read_csv(RAW_FILE)
    print(f"Loaded raw file with {len(df_raw)} rows")

    # Step 1: Clean columns
    df_cleaned = clean_company_table(df_raw)
    df_cleaned = df_cleaned[DEFAULT_COLUMNS]
    print(f"Cleaned to {len(df_cleaned)} company records")

    # Step 2: Save to CSV for manual upload
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_cleaned.to_csv(CLEANED_FILE, index=False)
    print(f"✅ Saved cleaned data to: {CLEANED_FILE}")

if __name__ == "__main__":
    run_pipeline()
