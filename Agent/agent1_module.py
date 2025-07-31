
import re
import json
from typing import Optional, TypedDict
from fuzzywuzzy import fuzz
from .shared import vectorstore, llm

class ProductState(TypedDict):
    product_name: str
    product_code: Optional[str]
    subsidy_level: Optional[str]

class ProductDetailAgent:
    def __init__(self):
        self.vectorstore = vectorstore
        self.llm = llm

    def find_best_matching_chunk(self, name: str, chunks) -> Optional[str]:
        best_score = 0
        best_chunk = None
        for doc in chunks:
            score = fuzz.partial_ratio(name.lower(), doc.page_content.lower())
            if score > best_score:
                best_score = score
                best_chunk = doc.page_content
        if best_score > 70:
            return best_chunk
        return None

    def extract_product_details(self, product_name: str) -> ProductState:
        def clean_product_name(name: str) -> str:
            name = re.sub(r'\b(SINGLE|TWIN|PACK|BOX|BAG|KG|G|ML|L)\b', '', name, flags=re.IGNORECASE)
            name = re.sub(r'[,&/()-]', ' ', name)
            return name.strip().lower()

        state: ProductState = {
            "product_name": product_name,
            "product_code": None,
            "subsidy_level": None
        }

        chunks = list(self.vectorstore.docstore._dict.values())
        valid_codes = {
            doc.metadata.get("product_code")
            for doc in chunks if doc.metadata.get("product_code")
        }

        cleaned_name = clean_product_name(product_name)
        matched_chunk = self.find_best_matching_chunk(cleaned_name, chunks)

        text_to_use = matched_chunk if matched_chunk else ""
        best_line = None
        if matched_chunk:
            for line in matched_chunk.split('\n'):
                if cleaned_name in line.lower():
                    best_line = line
                    break
            if best_line:
                text_to_use = best_line

        # Regex match
        product_code_match = re.search(r'\b\d-[A-Z]\d{2}\b', text_to_use)
        if product_code_match:
            product_code = product_code_match.group(0)
            if product_code in valid_codes:
                state["product_code"] = product_code
                first_digit = product_code.split("-")[0]
                state["subsidy_level"] = {
                    "7": "High",
                    "1": "Medium",
                    "2": "Low",
                    "3": "Low",
                    "4": "Low",
                    "5": "Country Food",
                    "8": "Seasonal Surface"
                }.get(first_digit, None)

        if not state["product_code"]:
            product_description = product_name
            relevant_chunks = self.vectorstore.similarity_search(product_description, k=30)

            reference_text = "\n\n".join(doc.page_content for doc in relevant_chunks)

            seen = set()
            category_hints = ""
            for doc in relevant_chunks:
                category = doc.metadata.get("category")
                code = doc.metadata.get("product_code")
                if not category or not code:
                    continue
                key = (category, code)
                if key not in seen:
                    category_hints += f"- {category} → Code: {code}\n"
                    seen.add(key)

            prompt = f"""
            You are a subsidy extraction assistant for Nutrition North Canada (NNC). 
            Your task is to analyze a product description, match it to a category in the provided NNC reference document, and extract the corresponding product code and subsidy level. 
            You should use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match. 
            You will be provided with a product description and an NNC reference document.

            Product Description: {product_description}

            NNC Reference Document: {reference_text}


            Follow these steps:

            1.  Carefully analyze the product description.
            2.  Review the NNC reference document to understand the different product categories and their associated product codes and subsidy levels.
            3.  Use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match.
                *   For example, the reference document lists "Bread products" (1-B04). Use your knowledge to understand that products like bagels, English muffins, bread rolls, raisin bread, hamburger buns, hot dog buns, pizza crusts, and frozen bread dough also fall under the "Bread products" category.
            4.  Extract the product code and subsidy level for the matched category.
            5.  Output the product code and subsidy level in the following JSON format:

            Expected Output Format:
            {{
            "product_code": "<NNC ID or null>",
            "subsidy_level": "<High/Medium/Low/Country Food/Seasonal Surface or null>"
            }}

            Here are the rules for determining the subsidy level:

            *   7 → High  
            *   1 → Medium  
            *   2, 3, 4 → Low  
            *   5 → Country Food  
            *   8 → Seasonal Surface  

            Here are some examples:

            Example 1:
            Input:
            product name = "Frozen vegetables"

            Output:
            {{
            "product_code": "7-A01",
            "subsidy_level": "High"
            }}

            Example 2:
            Input:
            product name = "Butter"

            Output:
            {{
            "product_code": "1-A01",
            "subsidy_level": "Medium"
            }}

            Example 3:
            Input:
            product name = "Fresh salmon"

            Output:
            {{
            "product_code": "5-C02",
            "subsidy_level": "Country Food"
            }}

            If you cannot find a matching category or the product description is unclear, output:
            {{
            "product_code": null,
            "subsidy_level": null
            }}
            """

            try:
                print("[DEBUG] Sending prompt to LLM...")
                response = self.llm.invoke(prompt)
                raw_text = response.content if hasattr(response, "content") else str(response)
                json_match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
                parsed = json.loads(json_match.group(0)) if json_match else {}

                code_from_llm = parsed.get("product_code")
                if code_from_llm in valid_codes:
                    state["product_code"] = code_from_llm
                    state["subsidy_level"] = parsed.get("subsidy_level")
                else:
                    print(f"LLM returned invalid or unrecognized code: {code_from_llm}. Ignored.")
            except Exception as e:
                print(f"Failed to extract JSON from LLM: {e}")

        if state["product_code"] and not state["subsidy_level"]:
            first_digit = state["product_code"].split("-")[0]
            state["subsidy_level"] = {
                "7": "High",
                "1": "Medium",
                "2": "Low",
                "3": "Low",
                "4": "Low",
                "5": "Country Food",
                "8": "Seasonal Surface"
            }.get(first_digit, None)

        if not state["product_code"]:
            print(f"Could not determine product code for: {product_name}")

        return state

