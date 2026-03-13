from fastapi import APIRouter
from app.api import api_predict

router = APIRouter()

router.include_router(api_predict.router, tags=["predict"])