"""Celery tasks for batch processing product predictions.

Defines a task that takes a community_id and a list of product names, runs
Agent1 and Agent2 for each, and returns the aggregated results.
"""

from typing import List, Dict, Optional
from .celery_app import celery_app
from .agent1_module import ProductDetailAgent
from .Agent2 import Agent2


@celery_app.task(name="agent.process_products", bind=True)
def process_products_task(self, community_id: str, product_names: List[str]) -> List[Dict]:
    agent1 = ProductDetailAgent()
    agent2 = Agent2(community_id.strip())

    results: List[Dict] = []
    for idx, product_name in enumerate(product_names):
        product_state = agent1.extract_product_details(product_name)
        if not product_state.get("subsidy_level"):
            # Keep position with placeholder if subsidy_level couldn't be determined
            results.append({
                "product_name": product_name,
                "product_code": None,
                "subsidy_level": None,
                "community_id": community_id,
                "discount_per_kg": None,
            })
            continue
        try:
            result = agent2.run(product_state)
        except Exception:
            result = None
        if result is None:
            results.append({
                "product_name": product_name,
                "product_code": product_state.get("product_code"),
                "subsidy_level": product_state.get("subsidy_level"),
                "community_id": community_id,
                "discount_per_kg": None,
            })
        else:
            results.append(result)
    return results
