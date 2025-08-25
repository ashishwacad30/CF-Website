

import sys
import json
import re
from .shared import vectorstore, query_llm
from Agent.agent1_module import ProductDetailAgent

"""Agent 2: Community subsidy lookup and aggregation.This module defines `Agent2`, which retrieves context for a given community ID
from a vector store, prompts an LLM to extract the discount per kg for a specified subsidy level, and combines that with product info produced by
`ProductDetailAgent`."""
class Agent2:
    """Agent that extracts discount information for a community.

    Given a `community_id`, the agent retrieves relevant context from the
    vector store and queries an LLM to extract the discount per kg for a
    specific subsidy level.
    """
    def __init__(self, community_id):
        """Initialize with a community identifier and prefetch context.

        Args:
            community_id: Community identifier string used for retrieval and
                table row matching in the LLM prompt.
        """
        self.community_id = community_id.strip()
        self.context = self.get_relevant_context()

    def get_relevant_context(self, top_k=20, max_words=2500) -> str:
        """Retrieve concatenated text context for the community.

        Args:
            top_k: Number of similar documents to retrieve from the store.
            max_words: Maximum word count to keep after concatenation.

        Returns:
            A single string containing the top-k results truncated to
            `max_words`, used as the table context in prompts.
        """
        results = vectorstore.similarity_search(self.community_id, k=top_k)
        combined = "\n".join([doc.page_content for doc in results if doc.page_content])

    # Truncate to max words (~token count)
        words = combined.split()
        if len(words) > max_words:
            combined = " ".join(words[:max_words])

        return combined

    def extract_discount_info(self, subsidy_level=None):
        """Ask the LLM to extract discount per kg for the given subsidy level.

        The prompt instructs the model to perform an exact match on the
        `community_id` and return a small JSON object with `discount_per_kg`.

        Args:
            subsidy_level: One of the recognized subsidy levels (e.g., High,
                Medium, Low, Seasonal). Can be None; the prompt still executes
                but may return "Not found".

        Returns:
            A dict with keys `community_id` and `discount_per_kg`.
        """
        prompt = f"""
        You are a smart assistant. From the table or data below, extract the discount per kg for a given community ID and subsidy level.

        The data is structured with the format:
        Community Name Community ID High Medium Low Seasonal

        Please perform an exact match on the Community ID, and return the value from the correct subsidy level column.

        Always respond in valid JSON like:
        {{
        "community_id": "...",
        "discount_per_kg": "..."
        }}

        Strictly follow these examples:

        Example 1:
        Input:
        community_id = "ON-NON-ATT"
        subsidy_level = "Medium"
        Table:
        Attawapiskat ON-NON-ATT 3.10 2.90 1.40 1.10

        Output:
        {{
        "community_id": "ON-NON-ATT",
        "discount_per_kg": "2.90"
        }}

        Example 2:
        Input:
        community_id = "MB-NMB-BRO"
        subsidy_level = "Low"
        Table:
        Brochet MB-NMB-BRO 3.10 2.90 1.40 1.10

        Output:
        {{
        "community_id": "MB-NMB-BRO",
        "discount_per_kg": "1.40"
        }}

        Example 3:
        Input:
        community_id = "AB-NAB-FCH"
        subsidy_level = "High"
        Table:
        Brochet MB-NMB-BRO 3.10 2.90 1.40 1.10

        Output:
        {{
        "community_id": "AB-NAB-FCH",
        "discount_per_kg": "3.10"
        }}
        Now, complete the following:

        Input:
        community_id = "{self.community_id}"
        subsidy_level = "{subsidy_level}"

        Table:
        {self.context}
        """
        result = query_llm(prompt)
        try:
            json_str = re.search(r'\{.*\}', result, re.DOTALL).group()
            return json.loads(json_str)
        except Exception as e:
            print("Failed to extract JSON:", e)
            return {
                "community_id": self.community_id,
                "discount_per_kg": "Not found"
            }

    def run(self, product_info):
        """Combine product info with community discount information.

        Args:
            product_info: Dict-like mapping from `ProductDetailAgent` including
                at least `subsidy_level`.

        Returns:
            A dict merging product info with `community_id` and
            `discount_per_kg` extracted for that subsidy level.
        """
        subsidy_level = product_info.get("subsidy_level")
        discount_info = self.extract_discount_info(subsidy_level=subsidy_level)
        final_info = {
            **product_info,
            "community_id": self.community_id,
            "discount_per_kg": discount_info.get("discount_per_kg", "Not found")
        }
        print("\nAgent2 is working:", final_info)
        return final_info

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m Agent.Agent2 <community_id> <product_name1> [<product_name2> ...]")
        sys.exit(1)

    community_id = sys.argv[1].strip()
    product_names = sys.argv[2:]

    agent1 = ProductDetailAgent()
    agent2 = Agent2(community_id)

    results = []

    for i, product_name in enumerate(product_names):
        print(f"\nProcessing Product {i+1}: {product_name}")

        product_state = agent1.extract_product_details(product_name)
        print("Agent1 is working:")
        print(product_state)

        if not product_state.get("subsidy_level"):
            print("Could not determine subsidy level. Skipping.")
            continue

        result = agent2.run(product_state)
        results.append(result)

    print("\nFinal Results Summary:")
    for r in results:
        print(json.dumps(r, indent=2))