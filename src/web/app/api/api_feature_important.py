from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import FeatureImportance, PathActivation

router = APIRouter(tags=["eda"])


@router.get("/feature-importance")
def feature_importance(db: Session = Depends(get_db)):
    activation = db.query(PathActivation).filter(PathActivation.is_active == True).first()  # noqa: E712
    if activation is None:
        raise HTTPException(status_code=404, detail="Chưa có model nào được active. Hãy chạy retrain trước.")

    run_id = activation.run_id
    rows = (
        db.query(FeatureImportance)
        .filter(FeatureImportance.run_id == run_id)
        .order_by(FeatureImportance.importance.desc())
        .all()
    )
    return {
        "run_id": run_id,
        "features": [{"name": r.feature_name, "importance": r.importance} for r in rows],
    }
