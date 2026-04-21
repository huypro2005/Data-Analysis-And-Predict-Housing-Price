from fastapi import APIRouter
from app.api import api_predict, api_retrain, api_eda, api_feature_important, api_gpt, api_gooing

router = APIRouter()
router.include_router(api_predict.router, tags=["predict"])
router.include_router(api_retrain.router)
router.include_router(api_eda.router)
router.include_router(api_gooing.router, tags=["geocode"])
router.include_router(api_feature_important.router)
router.include_router(api_gpt.router, tags=["chat"])
