from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, RootModel
from typing import List, Dict
from Agent.agent1_module import ProductDetailAgent
from Agent.Agent2 import Agent2
from Agent.tasks import process_products_task
from Agent.validation import validate_and_trigger_agents

app = FastAPI()
class LocationRequest(BaseModel):
    address: str
    community_name: str

class ProductItem(RootModel[Dict[str, str]]):
    pass

class PredictionRequest(BaseModel):
    order_id: str
    community_id: str
    product_names: List[ProductItem]

def format_response(order_id: str, community_id: str, raw_products: List[dict], order_item_ids: List[str]) -> dict:
    formatted_products = []
    for product, order_item_id in zip(raw_products, order_item_ids):
        # Rename discount_per_kg to subsidy_value if present
        subsidy_value = product.get("discount_per_kg") or product.get("subsidy_value")
        formatted_products.append({
            "product_name": product.get("product_name"),
            "product_code": product.get("product_code"),
            "subsidy_level": product.get("subsidy_level"),
            "community_id": community_id,
            "subsidy_value": subsidy_value,
            "order_item_id": order_item_id,
        })
    return {
        "order_id": order_id,
        "products": formatted_products
    }

@app.post("/predict")
def predict(request: PredictionRequest) -> dict:
    order_item_ids: List[str] = []
    product_names: List[str] = []
    for item in request.product_names:
        order_item_id, product_name_str = list(item.root.items())[0]
        order_item_ids.append(order_item_id)
        product_names.append(product_name_str)

    async_result = process_products_task.delay(request.community_id, product_names)

    try:
        results: List[dict] = async_result.get(timeout=300)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {e}")

    if not results:
        raise HTTPException(status_code=404, detail="No valid results generated.")

    return format_response(request.order_id, request.community_id, results, order_item_ids)

@app.post("/validate-address/")
def validate_address_endpoint(payload: LocationRequest):
    try:
        delivery_address = payload.address
        input_community_name = payload.community_name
        result = validate_and_trigger_agents(delivery_address, input_community_name)

        if result["status"] == "failed":
            raise HTTPException(status_code=400, detail=result["reason"])
        elif result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))