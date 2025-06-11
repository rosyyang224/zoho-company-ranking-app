import pandas as pd

def normalize_missing(val):
    """Convert empty strings and pandas NA to Python None."""
    if pd.isna(val) or str(val).strip().lower() in ["", "nan", "na", "<na>"]:
        return None
    return str(val).strip()


def preprocess_df(path):
    df = pd.read_csv(path, encoding="ISO-8859-1")
    df.columns = df.columns.str.strip()
    df.drop_duplicates(inplace=True)
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].map(normalize_missing)
    df = df.where(pd.notna(df), None)
    return df
