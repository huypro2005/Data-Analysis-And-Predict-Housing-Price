from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.service.predict_service import predict

router = APIRouter()


@router.post("/predict")
def predict_endpoint(data: dict, db: Session = Depends(get_db)):
    price_per_m2, total_price = predict(data, db_session=db)
    return {"predicted_price_per_m2": price_per_m2, "predicted_total_price": total_price}
