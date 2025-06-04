import pandas as pd
from config import DEFAULT_COLUMNS

def clean_company_table(df):
    df.columns = df.columns.str.strip().str.lower()

    df_cleaned = df[[
        "account name", "website", "shipping state",
        "shipping country", "employees", "rating", "major segment"
    ]].copy()

    df_cleaned.rename(columns={
        "account name": "name",
        "employees": "size",
        "rating": "funding_stage",
        "major segment": "modality",
        "shipping country": "country",
        "shipping state": "state"
    }, inplace=True)

    for col in df_cleaned.columns:
        df_cleaned[col] = df_cleaned[col].apply(
            lambda x: None if pd.isna(x) or str(x).strip().lower() in ["", "nan", "none"] else str(x).strip()
        )

    return df_cleaned[DEFAULT_COLUMNS]