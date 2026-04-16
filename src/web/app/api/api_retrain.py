from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.db.database import get_db
from app.db.models import ModelMetrics, TrainingRun

router = APIRouter(prefix="/retrain", tags=["retrain"])

DATA_PATH = str(BASE_DIR / "data" / "data.csv")


def do_retrain(data_path: str = DATA_PATH):
    """Hàm retrain dùng chung cho background task và scheduler."""
    from app.db.database import SessionLocal
    from app.retrain.retrain_service import RetrainOrchestrator

    db = SessionLocal()
    try:
        RetrainOrchestrator(db).run(data_path)
    except Exception as e:
        print(f"Retrain error: {e}")
    finally:
        db.close()


@router.post("/trigger")
def trigger_retrain(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Kích hoạt retrain thủ công. Trả 409 nếu đang có run đang chạy."""
    running = db.query(TrainingRun).filter(TrainingRun.status == "running").first()
    if running:
        raise HTTPException(
            status_code=409,
            detail=f"Retrain đang chạy (run_id={running.id})"
        )
    background_tasks.add_task(do_retrain, DATA_PATH)
    return {"message": "Retrain đã được kích hoạt"}


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    """Trạng thái retrain hiện tại và run gần nhất."""
    last_run = (
        db.query(TrainingRun)
        .order_by(TrainingRun.triggered_at.desc())
        .first()
    )
    is_running = last_run is not None and last_run.status == "running"
    last_info = None
    if last_run:
        last_info = {
            "id": last_run.id,
            "triggered_at": last_run.triggered_at,
            "status": last_run.status,
            "new_rows": last_run.new_rows,
            "model_replaced": last_run.model_replaced,
        }
    return {"status": "running" if is_running else "idle", "last_run": last_info}


@router.get("/history")
def get_history(page: int = 1, size: int = 10, db: Session = Depends(get_db)):
    """Lịch sử các lần retrain, phân trang, kèm metrics."""
    offset = (page - 1) * size
    runs = (
        db.query(TrainingRun)
        .order_by(TrainingRun.triggered_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )
    total = db.query(TrainingRun).count()
    items = []
    for r in runs:
        m = r.metrics
        items.append({
            "id": r.id,
            "triggered_at": r.triggered_at,
            "status": r.status,
            "new_rows": r.new_rows,
            "total_rows": r.total_rows,
            "duration_sec": r.duration_sec,
            "model_replaced": r.model_replaced,
            "metrics": {
                "rmse": m.rmse, "mae": m.mae, "r2": m.r2,
                "prev_rmse": m.prev_rmse, "prev_mae": m.prev_mae, "prev_r2": m.prev_r2,
            } if m else None,
        })
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/metrics/trend")
def get_metrics_trend(db: Session = Depends(get_db)):
    """Xu hướng RMSE/MAE/R2 qua các lần retrain thành công."""
    rows = (
        db.query(TrainingRun, ModelMetrics)
        .join(ModelMetrics, ModelMetrics.run_id == TrainingRun.id)
        .filter(TrainingRun.status == "success")
        .order_by(TrainingRun.triggered_at.asc())
        .all()
    )
    return {
        "runs": [
            {"run_id": run.id, "date": run.triggered_at, "rmse": m.rmse, "mae": m.mae, "r2": m.r2}
            for run, m in rows
        ]
    }
