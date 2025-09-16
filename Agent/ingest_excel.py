import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://cavtal_user:1234@localhost/cavtal_inventory"
)

file_path = "/home/ubuntu/CF-Website/CavTal Inventory for DataBase Construction.xlsx"

df = pd.read_excel(file_path, sheet_name="Sorted with New Vendor Info", header=3)

df.columns = (
    df.columns.str.strip()
    .str.replace('\n', '', regex=True)
    .str.replace(' ', '_', regex=True)
    .str.lower()
)

print("Columns after normalization:", df.columns.tolist())

required_cols = ["itemname", "nnc_id"]
available = [col for col in required_cols if col in df.columns]

if not available:
    raise ValueError(f"Required columns not found. Available columns: {df.columns.tolist()}")

df = df[available].copy()

for col in available:
    df[col] = df[col].astype(str).str.strip()

df.to_sql("product_catalog", engine, if_exists="replace", index=False)
print("Data loaded into PostgreSQL successfully.")
