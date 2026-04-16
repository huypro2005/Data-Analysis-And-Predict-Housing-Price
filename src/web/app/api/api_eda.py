from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.db.database import get_db
from app.db.models import District, DistrictPriceStats, PathActivation, PriceDistribution, RealEstateType

router = APIRouter(prefix="/eda", tags=["eda"])


def _get_active_run_id(db: Session) -> int:
    activation = db.query(PathActivation).filter(PathActivation.is_active == True).first()  # noqa: E712
    if activation is None:
        raise HTTPException(status_code=404, detail="Chưa có model nào được active. Hãy chạy retrain trước.")
    return activation.run_id, activation


@router.get("/price-distribution")
def price_distribution(db: Session = Depends(get_db)):
    run_id, _ = _get_active_run_id(db)
    rows = (
        db.query(PriceDistribution)
        .filter(PriceDistribution.run_id == run_id)
        .all()
    )
    bins = [
        {"label": r.price_range, "min": r.min_range, "max": r.max_range, "count": r.samples_count}
        for r in rows
    ]
    return {"run_id": run_id, "bins": bins}


@router.get("/district-property-type")
def district_property_type(db: Session = Depends(get_db)):
    run_id, _ = _get_active_run_id(db)
    rows = db.query(DistrictPriceStats).filter(DistrictPriceStats.run_id == run_id).all()
    data = []
    for r in rows:
        try:
            district_label = District.from_code(r.district_code).label
        except ValueError:
            district_label = str(r.district_code)
        try:
            prop_label = RealEstateType.from_code(r.property_code).label
        except ValueError:
            prop_label = str(r.property_code)
        data.append({
            "district": district_label,
            "property_type": prop_label,
            "median_price": r.median_price,
            "sample_count": r.sample_count,
        })
    return {"run_id": run_id, "data": data}


@router.get("/scatter/version")
def scatter_version(db: Session = Depends(get_db)):
    run_id, activation = _get_active_run_id(db)
    updated_at = activation.run.triggered_at if activation.run else None
    return {"run_id": run_id, "updated_at": updated_at}


@router.get("/scatter/file")
def scatter_file(db: Session = Depends(get_db)):
    _, activation = _get_active_run_id(db)
    from pathlib import Path as _Path
    _p = _Path(activation.path_scatter)
    scatter_abs = _p if _p.is_absolute() else BASE_DIR / activation.path_scatter
    if not scatter_abs.exists():
        raise HTTPException(status_code=404, detail="File scatter không tồn tại.")
    return FileResponse(
        str(scatter_abs),
        media_type="text/csv",
        filename="scatter.csv",
        headers={"Cache-Control": "max-age=86400"},
    )
