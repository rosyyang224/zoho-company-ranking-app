import pandas as pd

def extract_top_cgt_companies(xlsx_path, output_csv="output/top_cgt_companies.csv"):
    df = pd.read_excel(xlsx_path)

    # Filter for CGT Pipeline Biotherapeutics
    cgt_df = df[df["Account Type"] == "CGT Pipeline Biotherapeutics"]

    # Select needed columns
    cgt_df = cgt_df[["Account Name", "Website"]].dropna(subset=["Account Name"]).drop_duplicates()

    # Rename columns for consistency
    cgt_df.rename(columns={"Account Name": "Company", "Website": "Original Website"}, inplace=True)

    # Take top N
    cgt_df.to_csv(output_csv, index=False)
    print(f"✅ ExtractedCGT companies to {output_csv}")

if __name__ == "__main__":
    extract_top_cgt_companies("Leads_2025_05_09 - Working file - Copy.xlsx")
