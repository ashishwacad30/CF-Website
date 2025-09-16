from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, RootModel
from typing import List, Dict
from agent1_module import ProductDetailAgent
from Agent2 import Agent2
from tasks import process_products_task
from validation import validate_and_trigger_agents

app = FastAPI()
class LocationRequest(BaseModel):
    address: str
    community_name: str

class ProductItem(RootModel[Dict[str, str]]):
    pass

class PredictionRequest(BaseModel):
    cart_id: str
    community_id: str
    product_names: List[ProductItem]

def format_response(cart_id: str, community_id: str, raw_products: List[dict], cart_item_ids: List[str]) -> dict:
    formatted_products = []
    for product, cart_item_id in zip(raw_products, cart_item_ids):
        # Rename discount_per_kg to subsidy_value if present
        subsidy_value = product.get("discount_per_kg") or product.get("subsidy_value")
        formatted_products.append({
            "product_name": product.get("product_name"),
            "product_code": product.get("product_code"),
            "subsidy_level": product.get("subsidy_level"),
            "community_id": community_id,
            "subsidy_value": subsidy_value,
            "cart_item_id": cart_item_id,
        })
    return {
        "cart_id": cart_id,
        "products": formatted_products
    }


@app.post("/predict")
def predict(request: PredictionRequest) -> dict:
    async_result = process_products_task.delay(
        request.cart_id,
        request.community_id,
        [p.dict() for p in request.product_names]  # send full dicts
    )
    results = async_result.get()  # wait for worker result
    return results

    try:
        results: List[dict] = async_result.get(timeout=300)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {e}")

    if not results:
        raise HTTPException(status_code=404, detail="No valid results generated.")

    return format_response(request.cart_id, request.community_id, results, cart_item_ids)

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