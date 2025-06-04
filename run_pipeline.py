import os
import pandas as pd
from sqlalchemy import create_engine, text
from clean_company_data import clean_company_table
from config import RAW_FILE, SUPABASE_DB_URL, DEFAULT_COLUMNS

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
    # print(SUPABASE_DB_URL)
    engine = create_engine(SUPABASE_DB_URL)

    if not os.path.exists(RAW_FILE):
        print(f"Raw file not found: {RAW_FILE}")
        return

    df_raw = pd.read_csv(RAW_FILE)
    print(f"Loaded raw file with {len(df_raw)} rows")

    df_cleaned = clean_company_table(df_raw)
    df_cleaned = df_cleaned[DEFAULT_COLUMNS]
    print(f"Cleaned to {len(df_cleaned)} company records")

    insert_companies_to_supabase(df_cleaned, engine)
    print("Synced to Supabase database")

if __name__ == "__main__":
    run_pipeline()
