import pandas as pd

def clean_company_table(df):
    df.columns = df.columns.str.strip().str.lower()

    df_cleaned = df[[
        "account name", "website", "shipping city", "shipping state",
        "shipping country", "region", "employees", "rating", "major segment"
    ]].copy()

    df_cleaned.rename(columns={
        "account name": "name",
        "employees": "size",
        "rating": "funding_stage",
        "major segment": "modality",
        "shipping city": "city",
        "shipping state": "state",
        "shipping country": "country"
    }, inplace=True)

    def resolve_location(row):
        if pd.notnull(row["city"]) and pd.notnull(row["state"]) and pd.notnull(row["country"]):
            return f"{row['city']}, {row['state']}, {row['country']}"
        elif pd.notnull(row["region"]):
            return row["region"]
        else:
            return "Unknown"

    df_cleaned["location"] = df_cleaned.apply(resolve_location, axis=1)

    return df_cleaned[["name", "website", "location", "size", "funding_stage", "modality"]]
