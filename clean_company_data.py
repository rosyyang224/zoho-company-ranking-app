import pandas as pd

def clean_company_table(input_csv, output_csv):
    df = pd.read_csv(input_csv)

    # Extract relevant fields
    df_cleaned = df[[
        "Account Name", "Website", "Shipping City", "Shipping State",
        "Shipping Country", "Region", "Employees", "Rating", "Major segment"
    ]].copy()

    # Rename for clarity
    df_cleaned.rename(columns={
        "Account Name": "Name",
        "Employees": "Size",
        "Rating": "Funding Stage",
        "Major segment": "Modality",
        "Shipping City": "City",
        "Shipping State": "State",
        "Shipping Country": "Country"
    }, inplace=True)

    # Construct fallback location
    def resolve_location(row):
        if pd.notnull(row["City"]) and pd.notnull(row["State"]) and pd.notnull(row["Country"]):
            return f"{row['City']}, {row['State']}, {row['Country']}"
        elif pd.notnull(row["Region"]):
            return row["Region"]
        else:
            return "Unknown"

    df_cleaned["Location"] = df_cleaned.apply(resolve_location, axis=1)

    # Final columns
    df_cleaned = df_cleaned[[
        "Name", "Website", "Location", "Size", "Funding Stage", "Modality"
    ]]

    # Save output
    df_cleaned.to_csv(output_csv, index=False)
    print(f"Cleaned company table saved to {output_csv}")

# Example usage:
if __name__ == "__main__":
    clean_company_table("Accounts_2025_06_03.csv", "Cleaned_Company_Table.csv")
