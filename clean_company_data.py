import pandas as pd
from config import DEFAULT_COLUMNS

def normalize_missing(val):
    """Convert empty strings and pandas NA to Python None."""
    if pd.isna(val) or str(val).strip().lower() in ["", "nan", "na", "<na>"]:
        return None
    return str(val).strip()


def preprocess_df(path):
    df = pd.read_csv(path, encoding="ISO-8859-1")
    df.dropna(axis=1, how="all", inplace=True)
    df.columns = df.columns.str.strip()
    df.drop_duplicates(inplace=True)
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].map(normalize_missing)
    df = df.where(pd.notna(df), None)
    return df

def clean_company_table(df):
    df.columns = df.columns.str.strip().str.lower()

    df_cleaned = df[[
        "account name", "website", "billing state",
        "billing country", "company size (fte)", "funding stage", "major segment"
    ]].copy()

    df_cleaned.rename(columns={
        "account name": "name",
        "company size (fte)": "size",
        "funding stage": "funding_stage",
        "major segment": "modality",
        "billing country": "country",
        "billing state": "state"
    }, inplace=True)

    for col in df_cleaned.columns:
        df_cleaned[col] = df_cleaned[col].apply(
            lambda x: None if pd.isna(x) or str(x).strip().lower() in ["", "nan", "none"] else str(x).strip()
        )

    return df_cleaned[DEFAULT_COLUMNS]