from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from Agent.agent1_module import ProductDetailAgent
from Agent.Agent2 import Agent2
from Agent.validation import validate_and_trigger_agents

app = FastAPI()

class LocationRequest(BaseModel):
    address: str
    community_name: str

class PredictionRequest(BaseModel):
    community_id: str
    product_names: List[str]

class PredictionResponse(BaseModel):
    product_name: str
    product_code: str
    subsidy_level: str
    community_id: str
    discount_per_kg: str

@app.post("/predict")
def predict(request: PredictionRequest) -> List[dict]:
    agent1 = ProductDetailAgent()
    agent2 = Agent2(request.community_id.strip())
    results = []

    for i, product_name in enumerate(request.product_names):
        print(f"\nProcessing Product {i+1}: {product_name}")

        product_state = agent1.extract_product_details(product_name)
        print("Agent1 is working:")
        print(product_state)

        if not product_state.get("subsidy_level"):
            print("Could not determine subsidy level. Skipping.")
            continue

        result = agent2.run(product_state)
        results.append(result)

    if not results:
        raise HTTPException(status_code=404, detail="No valid results generated.")

    return results

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