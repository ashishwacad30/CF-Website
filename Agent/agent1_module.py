# import re
# import json
# from typing import Optional, TypedDict
# from fuzzywuzzy import fuzz
# from .shared import vectorstore, llm

# class ProductState(TypedDict):
#     product_name: str
#     product_code: Optional[str]
#     subsidy_level: Optional[str]

# class ProductDetailAgent:
#     def __init__(self):
#         self.vectorstore = vectorstore
#         self.llm = llm

#     def find_best_matching_chunk(self, name: str, chunks) -> Optional[str]:
#         best_score = 0
#         best_chunk = None
#         for doc in chunks:
#             score = fuzz.partial_ratio(name.lower(), doc.page_content.lower())
#             if score > best_score:
#                 best_score = score
#                 best_chunk = doc.page_content
#         if best_score > 70:
#             return best_chunk
#         return None

#     def extract_product_details(self, product_name: str) -> ProductState:
#         state: ProductState = {
#             "product_name": product_name,
#             "product_code": None,
#             "subsidy_level": None
#         }

#         chunks = list(self.vectorstore.docstore._dict.values())
#         matched_chunk = self.find_best_matching_chunk(product_name, chunks)

#         if matched_chunk:
#             best_line = None
#             lines = matched_chunk.split('\n')
#             for line in lines:
#                 if product_name.lower() in line.lower():  # ← improved match
#                     best_line = line
#                     break

#             text_to_use = best_line if best_line else matched_chunk

#             product_code_match = re.search(r'\b\d-[A-Z]\d{2}\b', text_to_use)
#             if product_code_match:
#                 product_code = product_code_match.group(0)
#                 state["product_code"] = product_code

#                 first_digit = product_code.split("-")[0]
#                 subsidy = {
#                     "7": "High",
#                     "1": "Medium",
#                     "2": "Low",
#                     "3": "Low",
#                     "4": "Low",
#                     "5": "Country Food",
#                     "8": "Seasonal Surface"
#                 }.get(first_digit, None)

#                 state["subsidy_level"] = subsidy
#             else:
#                 product_description = product_name
#                 combined_reference = "\n\n".join(doc.page_content for doc in chunks[:20])  # Top N chunks

#                 prompt = f"""
# You are a subsidy extraction assistant for Nutrition North Canada (NNC). 
# Your task is to analyze a product description, match it to a category in the provided NNC reference document, and extract the corresponding product code and subsidy level. 
# You should use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match. 
# You will be provided with a product description and an NNC reference document.

# Product Description: {product_description}

# NNC Reference Document: {combined_reference}

# Follow these steps:

# 1.  Carefully analyze the product description.
# 2.  Review the NNC reference document to understand the different product categories and their associated product codes and subsidy levels.
# 3.  Use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match.
#     *   For example, the reference document lists "Bread products" (1-B04). Use your knowledge to understand that products like bagels, English muffins, bread rolls, raisin bread, hamburger buns, hot dog buns, pizza crusts, and frozen bread dough also fall under the "Bread products" category.
# 4.  Extract the product code and subsidy level for the matched category.
# 5.  Output the product code and subsidy level in the following JSON format:

# Expected Output Format:
# {{
# "product_code": "<NNC ID or null>",
# "subsidy_level": "<High/Medium/Low/Country Food/Seasonal Surface or null>"
# }}

# Here are the rules for determining the subsidy level:

# *   7 → High  
# *   1 → Medium  
# *   2, 3, 4 → Low  
# *   5 → Country Food  
# *   8 → Seasonal Surface  

# Here are some examples:

# Example 1:
# Input:
# product name = "Frozen vegetables"

# Output:
# {{
# "product_code": "7-A01",
# "subsidy_level": "High"
# }}

# Example 2:
# Input:
# product name = "Butter"

# Output:
# {{
# "product_code": "1-A01",
# "subsidy_level": "Medium"
# }}

# Example 3:
# Input:
# product name = "Fresh salmon"

# Output:
# {{
# "product_code": "5-C02",
# "subsidy_level": "Country Food"
# }}

# If you cannot find a matching category or the product description is unclear, output:
# {{
# "product_code": null,
# "subsidy_level": null
# }}
#                 """
#                 response = self.llm.invoke(prompt)
#                 raw_text = response.content if hasattr(response, "content") else str(response)

#                 try:
#                     json_match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
#                     json_str = json_match.group(0) if json_match else "{}"
#                     parsed = json.loads(json_str)

#                     state["product_code"] = parsed.get("product_code")
#                     state["subsidy_level"] = parsed.get("subsidy_level")
#                 except Exception as e:
#                     print(f"Failed to extract JSON: {e}")
#         else:
#             # No fuzzy match found, try LLM directly
#             product_description = product_name
            
#             # Use similarity search to get more relevant chunks for the LLM
#             relevant_chunks = self.vectorstore.similarity_search(product_description, k=30)
#             combined_reference = "\n\n".join(doc.page_content for doc in relevant_chunks)

#             prompt = f"""
# You are a subsidy extraction assistant for Nutrition North Canada (NNC). 
# Your task is to analyze a product description, match it to a category in the provided NNC reference document, and extract the corresponding product code and subsidy level. 
# You should use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match. 
# You will be provided with a product description and an NNC reference document.

# Product Description: {product_description}

# NNC Reference Document: {combined_reference}

# Follow these steps:

# 1.  Carefully analyze the product description.
# 2.  Review the NNC reference document to understand the different product categories and their associated product codes and subsidy levels.
# 3.  Use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match.
#     *   For example, the reference document lists "Bread products" (1-B04). Use your knowledge to understand that products like bagels, English muffins, bread rolls, raisin bread, hamburger buns, hot dog buns, pizza crusts, and frozen bread dough also fall under the "Bread products" category.
# 4.  Extract the product code and subsidy level for the matched category.
# 5.  Output the product code and subsidy level in the following JSON format:

# Expected Output Format:
# {{
# "product_code": "<NNC ID or null>",
# "subsidy_level": "<High/Medium/Low/Country Food/Seasonal Surface or null>"
# }}

# Here are the rules for determining the subsidy level:

# *   7 → High  
# *   1 → Medium  
# *   2, 3, 4 → Low  
# *   5 → Country Food  
# *   8 → Seasonal Surface  

# Here are some examples:

# Example 1:
# Input:
# product name = "Frozen vegetables"

# Output:
# {{
# "product_code": "7-A01",
# "subsidy_level": "High"
# }}

# Example 2:
# Input:
# product name = "Butter"

# Output:
# {{
# "product_code": "1-A01",
# "subsidy_level": "Medium"
# }}

# Example 3:
# Input:
# product name = "Fresh salmon"

# Output:
# {{
# "product_code": "5-C02",
# "subsidy_level": "Country Food"
# }}

# If you cannot find a matching category or the product description is unclear, output:
# {{
# "product_code": null,
# "subsidy_level": null
# }}
#             """
#             response = self.llm.invoke(prompt)
#             raw_text = response.content if hasattr(response, "content") else str(response)

#             try:
#                 json_match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
#                 json_str = json_match.group(0) if json_match else "{}"
#                 parsed = json.loads(json_str)

#                 state["product_code"] = parsed.get("product_code")
#                 state["subsidy_level"] = parsed.get("subsidy_level")
#             except Exception as e:
#                 print(f"Failed to extract JSON: {e}")

#         return state


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
        return best_chunk if best_score > 70 else None

    def build_prompt(self, product_description: str, reference_document: str) -> str:
        return f"""
You are a subsidy extraction assistant for Nutrition North Canada (NNC). 
Your task is to analyze a product description, match it to a category in the provided NNC reference document, and extract the corresponding product code and subsidy level. 
You should use your knowledge and the NNC reference document to find the closest matching category for the user's product. Even if the product isn't explicitly listed, use common examples and your understanding of category-product relationships to make the best match. 
You will be provided with a product description and an NNC reference document.

Product Description: {product_description}

NNC Reference Document: {reference_document}

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

    def extract_product_details(self, product_name: str) -> ProductState:
        state: ProductState = {
            "product_name": product_name,
            "product_code": None,
            "subsidy_level": None
        }

        chunks = list(self.vectorstore.docstore._dict.values())
        matched_chunk = self.find_best_matching_chunk(product_name, chunks)

        if matched_chunk:
            best_line = next((line for line in matched_chunk.split('\n') if product_name.lower() in line.lower()), None)
            text_to_use = best_line if best_line else matched_chunk

            product_code_match = re.search(r'\b\d-[A-Z]\d{2}\b', text_to_use)
            if product_code_match:
                product_code = product_code_match.group(0)
                state["product_code"] = product_code

                first_digit = product_code.split("-")[0]
                subsidy = {
                    "7": "High",
                    "1": "Medium",
                    "2": "Low",
                    "3": "Low",
                    "4": "Low",
                    "5": "Country Food",
                    "8": "Seasonal Surface"
                }.get(first_digit, None)

                state["subsidy_level"] = subsidy
                return state  # ← early return if exact match worked

        # Fallback to LLM with vectorstore search if no fuzzy match or no code found
        relevant_chunks = self.vectorstore.similarity_search(product_name, k=30)
        combined_reference = "\n\n".join(doc.page_content for doc in relevant_chunks)

        prompt = self.build_prompt(product_name, combined_reference)
        response = self.llm.invoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)

        try:
            json_match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else "{}"
            parsed = json.loads(json_str)

            state["product_code"] = parsed.get("product_code")
            state["subsidy_level"] = parsed.get("subsidy_level")
        except Exception as e:
            print(f"Failed to extract JSON: {e}")

        return state


