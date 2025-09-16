
import os, re, json
from typing import Union, Optional, TypedDict, List, Tuple
import pandas as pd
from rapidfuzz import fuzz, process
from sqlalchemy import create_engine
import os


"""Agent 1: Resolve product names to NNC codes and subsidy levels. This module defines `ProductDetailAgent`, which loads a product catalog from an
    Excel workbook, normalizes and fuzzy-matches product names, and returns the corresponding NNC product code with an inferred subsidy level.
    Public API:
    - `ProductState` -output structure
    - `ProductDetailAgent.extract_product_details` -main entry point
    - `ProductDetailAgent.suggest_top_products` -helper for top-K suggestions
"""

class ProductState(TypedDict):
    product_name: str
    product_code: Optional[str]
    subsidy_level: Optional[str]

class ProductDetailAgent:
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or "postgresql+psycopg2://cavtal_user:1234@localhost/cavtal_inventory"
        self.df = self._load_sql()
        self.subsidy_by_prefix = {
            "7": "High",
            "1": "Medium",
            "2": "Low",
            "3": "Low",
            "4": "Low",
            "5": "Country Food",
            "8": "Seasonal Surface",
        }

    def _normalize_name(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        lowered = text.lower()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _load_sql(self) -> pd.DataFrame:
        """Load product catalog from PostgreSQL instead of Excel."""
        engine = create_engine(self.db_url)
        df = pd.read_sql("SELECT itemname, nnc_id FROM product_catalog", engine)
        df = df.dropna(subset=["itemname", "nnc_id"]).copy()
        df["ItemName"] = df["itemname"].astype(str).map(lambda s: s.strip())
        df["NNC ID"] = df["nnc_id"].astype(str).map(lambda s: s.strip())
        df["_name_norm"] = df["ItemName"].map(self._normalize_name)
        return df

    def suggest_top_products(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        choices = self.df["ItemName"].tolist()
        results = process.extract(query, choices, scorer=fuzz.WRatio, limit=top_k)
        return [(choice, float(score)) for choice, score, _ in results]

    def _pick_best_row(self, product_name: str) -> Optional[pd.Series]:
        norm_query = self._normalize_name(product_name)
        exact_matches = self.df[self.df["_name_norm"] == norm_query]
        if not exact_matches.empty:
            return exact_matches.iloc[0]

        best = process.extractOne(product_name, self.df["ItemName"].tolist(), scorer=fuzz.WRatio)
        if best is None:
            return None
        best_choice, best_score, _ = best
        if best_score < 70:
            return None
        row = self.df[self.df["ItemName"] == best_choice]
        return row.iloc[0] if not row.empty else None

    def extract_product_details(self, product_names: Union[str, List[str]]) -> Union[ProductState, List[ProductState]]:
        """
        Extract NNC product code and subsidy level for one or multiple product names.
        Args:
            product_names: A single product name (str) or a list of product names (List[str]).
        Returns:
            - If input is str: a single ProductState dict
            - If input is List[str]: a list of ProductState dicts
        """

        def process_single(product_name: str) -> ProductState:
            state: ProductState = {
                "product_name": product_name,
                "product_code": None,
                "subsidy_level": None,
            }

            row = self._pick_best_row(product_name)
            if row is None:
                return state

            product_code = str(row["NNC ID"]).strip()
            state["product_code"] = product_code if product_code else None

            first_digit = None
            m = re.match(r"^(\d+)-", product_code)
            if m:
                first_digit = m.group(1)
            if first_digit and first_digit in self.subsidy_by_prefix:
                state["subsidy_level"] = self.subsidy_by_prefix[first_digit]
            else:
                state["subsidy_level"] = None

            return state

        # Handle multiple products
        if isinstance(product_names, list):
            return [process_single(name) for name in product_names]
        else:
            return process_single(product_names)