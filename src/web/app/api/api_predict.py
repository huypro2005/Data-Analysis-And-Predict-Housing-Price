from fastapi import APIRouter
from app.service.predict_service import predict

router = APIRouter()

@router.post("/predict")
def predict_endpoint(data: dict):
    price_per_m2, total_price = predict(data)
    return {"predicted_price_per_m2": price_per_m2, "predicted_total_price": total_price}