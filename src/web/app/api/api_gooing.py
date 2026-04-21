from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.service.goong import get_coordinates_from_goong
router = APIRouter()

@router.get("/geocode")
def geocode_endpoint(address: str, db: Session = Depends(get_db)):
    result = get_coordinates_from_goong(address)
    if result:
        return {"address": result['address'], "x": result['x'], "y": result['y']}
    else:
        return {"error": "Unable to geocode the provided address."}