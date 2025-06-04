import os
import pandas as pd

INPUT_DIR = "data"
RAW_FILE = os.path.join(INPUT_DIR, "Accounts_2025_06_03.csv")
OUTPUT_DIR = "output"
CLEANED_FILE = os.path.join(OUTPUT_DIR, "Cleaned_Company_Table.csv")

def clean_company_table(df):
    df_cleaned = df[[
        "Account Name", "Website", "Shipping City", "Shipping State",
        "Shipping Country", "Region", "Employees", "Rating", "Major segment"
    ]].copy()

    df_cleaned.rename(columns={
        "Account Name": "Name",
        "Employees": "Size",
        "Rating": "Funding Stage",
        "Major segment": "Modality",
        "Shipping City": "City",
        "Shipping State": "State",
        "Shipping Country": "Country"
    }, inplace=True)

    def resolve_location(row):
        if pd.notnull(row["City"]) and pd.notnull(row["State"]) and pd.notnull(row["Country"]):
            return f"{row['City']}, {row['State']}, {row['Country']}"
        elif pd.notnull(row["Region"]):
            return row["Region"]
        else:
            return "Unknown"

    df_cleaned["Location"] = df_cleaned.apply(resolve_location, axis=1)

    return df_cleaned[["Name", "Website", "Location", "Size", "Funding Stage", "Modality"]]


def run_pipeline():
    print("Starting pipeline...")

    # Step 1: Read raw file
    if not os.path.exists(RAW_FILE):
        print(f"Raw file not found: {RAW_FILE}")
        return

    df_raw = pd.read_csv(RAW_FILE)
    print(f"Loaded raw file with {len(df_raw)} rows")

    # Step 2: Clean
    df_cleaned = clean_company_table(df_raw)
    print(f"Cleaned data to {len(df_cleaned)} companies")

    # Step 3: Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_cleaned.to_csv(CLEANED_FILE, index=False)
    print(f"Saved cleaned company table to {CLEANED_FILE}")


if __name__ == "__main__":
    run_pipeline()
