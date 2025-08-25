import os
import re
import json
from typing import Optional, TypedDict, List, Tuple
import pandas as pd
from rapidfuzz import fuzz, process

"""Agent 1: Resolve product names to NNC codes and subsidy levels. This module defines `ProductDetailAgent`, which loads a product catalog from an
Excel workbook, normalizes and fuzzy-matches product names, and returns the corresponding NNC product code with an inferred subsidy level.
Public API:
- `ProductState` -output structure
- `ProductDetailAgent.extract_product_details` -main entry point
- `ProductDetailAgent.suggest_top_products` -helper for top-K suggestions
"""
class ProductState(TypedDict):
    """Structured result for product detail extraction.
    Keys:
    - product_name: Original query string provided by the caller.
    - product_code: NNC code (e.g., "7-A01"), or None if no suitable match.
    - subsidy_level: One of {"High", "Medium", "Low", "Country Food",
      "Seasonal Surface"}, or None if undetermined.
    """
    product_name: str
    product_code: Optional[str]
    subsidy_level: Optional[str]

class ProductDetailAgent:
    """Agent for resolving product names to NNC codes and subsidy levels. The agent loads an Excel workbook containing product names and NNC IDs,
    normalizes text, performs exact or fuzzy matching against the catalog, and infers the subsidy level from the NNC ID prefix.
    """
    def __init__(self, excel_path: Optional[str] = None):
        """Initialize the agent and load the Excel catalog.
        Args:
            excel_path: Optional explicit path to the Excel workbook. If not
                provided, falls back to the `CAVTAL_EXCEL_PATH` environment
                variable, then a repo-local default path.
        """
        self.excel_path = excel_path or os.getenv("CAVTAL_EXCEL_PATH") or \
            "/Users/ashish/Downloads/Agentic-AI/CavTal Inventory for DataBase Construction.xlsx"
        self.df = self._load_excel(self.excel_path)
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
        """Return a normalized representation of a name for matching. 
        Lowercases, removes non-alphanumeric characters (except spaces), and collapses repeated whitespace.
        Args:
            text: Arbitrary input text (may be non-string).
        Returns:
            Normalized string suitable for exact/hashed comparisons.
        """
        if not isinstance(text, str):
            return ""
        lowered = text.lower()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    def _load_excel(self, path: str) -> pd.DataFrame:
        """Load and coerce an Excel workbook into a standardized DataFrame.The loader is resilient to header variability across sheets. It first
        attempts straightforward reads with column renaming; if that fails, it scans for a header row heuristically and reconstructs the DataFrame.
        Required output columns: `ItemName`, `NNC ID`.
        Args:
            path: Filesystem path to the Excel workbook.
        Returns:
            A cleaned DataFrame containing `ItemName`, `NNC ID`, and an
            auxiliary `_name_norm` column.
        """
        def normalize_header(name: str) -> str:
            if not isinstance(name, str):
                return ""
            return re.sub(r"\s+", " ", name.strip()).lower()
            
        def try_coerce_columns(df_in: pd.DataFrame) -> Optional[pd.DataFrame]:
            header_variants = {
                "itemname": "ItemName",
                "item name": "ItemName",
                "item": "ItemName",
                "product": "ItemName",
                "product name": "ItemName",
                "nnc id": "NNC ID",
                "nnc": "NNC ID",
                "nncid": "NNC ID",
                "nnc code": "NNC ID",
            }
            rename: dict = {}
            for c in df_in.columns:
                norm = normalize_header(c)
                if norm in header_variants:
                    rename[c] = header_variants[norm]
            df_tmp = df_in.rename(columns=rename)
            if {"ItemName", "NNC ID"}.issubset(set(df_tmp.columns)):
                return df_tmp
            return None

        try:
            with pd.ExcelFile(path) as xls:
                for sheet in xls.sheet_names:
                    try:
                        df_raw = pd.read_excel(xls, sheet_name=sheet, dtype=str)
                    except Exception:
                        continue
                    df_try = try_coerce_columns(df_raw)
                    if df_try is not None:
                        df = df_try
                        break
                else:
                    found = None
                    for sheet in xls.sheet_names:
                        try:
                            df_raw = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=str)
                        except Exception:
                            continue
                        for i in range(min(len(df_raw), 50)):
                            row_vals = [str(v) for v in df_raw.iloc[i].tolist()]
                            row_norm = [normalize_header(v) for v in row_vals]
                            if ("itemname" in row_norm or "item name" in row_norm or "product name" in row_norm or "product" in row_norm) and \
                               ("nnc id" in row_norm or "nnc" in row_norm or "nnc code" in row_norm or "nncid" in row_norm):
                                df_headed = df_raw.iloc[i+1:].copy()
                                df_headed.columns = df_raw.iloc[i].tolist()
                                df_headed = df_headed.dropna(how='all', axis=1)
                                df_try = try_coerce_columns(df_headed)
                                if df_try is not None:
                                    found = df_try
                                break
                        if found is not None:
                            break
                    if found is None:
                        raise RuntimeError("Could not find columns 'ItemName' and 'NNC ID' in any sheet.")
                    df = found
        except Exception as e:
            raise

        df = df.dropna(subset=["ItemName", "NNC ID"]).copy()
        df["ItemName"] = df["ItemName"].astype(str).map(lambda s: s.strip())
        df["NNC ID"] = df["NNC ID"].astype(str).map(lambda s: s.strip())
        df["_name_norm"] = df["ItemName"].astype(str).map(self._normalize_name)
        return df

    def suggest_top_products(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return top-K fuzzy matches from the catalog for a query string.Uses RapidFuzz WRatio scorer to rank `ItemName` candidates.
        Args:
            query: Free-form product name input.
            top_k: Number of top suggestions to return.
        Returns:
            List of (choice, score) tuples, where score is a float similarity
            in [0, 100].
        """
        choices = self.df["ItemName"].astype(str).tolist()
        results = process.extract(
            query,
            choices,
            scorer=fuzz.WRatio,
            limit=top_k,
        )
        return [(choice, float(score)) for choice, score, _ in results]

    def _pick_best_row(self, product_name: str) -> Optional[pd.Series]:
        """Select the best matching catalog row for a product name.
        Strategy:
        1. Exact match on normalized name (`_name_norm`).
        2. Fallback to fuzzy match (WRatio) over `ItemName`, accepting only if
           the score is at least 70.
        Args:
            product_name: The user-provided product name.
        Returns:
            A row (`pd.Series`) of the best match, or None if not acceptable.
        """
        norm_query = self._normalize_name(product_name)
        exact_matches = self.df[self.df["_name_norm"] == norm_query]
        if not exact_matches.empty:
            return exact_matches.iloc[0]

        best = process.extractOne(
            product_name,
            self.df["ItemName"].astype(str).tolist(),
            scorer=fuzz.WRatio,
        )
        if best is None:
            return None
        best_choice, best_score, _ = best
        if best_score < 70:
            return None
        row = self.df[self.df["ItemName"].astype(str) == best_choice]
        return row.iloc[0] if not row.empty else None

    def extract_product_details(self, product_name: str) -> ProductState:
        """Extract NNC product code and subsidy level for a product name.
        This is the primary API method. It locates the best matching catalog
        entry, reads the `NNC ID`, and infers the subsidy level from the first
        digit prior to the dash via `subsidy_by_prefix`.
        Args:
            product_name: The user-provided product name.
        Returns:
            ProductState containing the original name, resolved code, and
            derived subsidy level (or None values when not found).
        """
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

