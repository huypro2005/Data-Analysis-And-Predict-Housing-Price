from datetime import datetime
from pydantic import BaseModel


class PredictInput(BaseModel):
    loai_nha_dat: int
    dia_chi: int
    dien_tich: float
    mat_tien: float | None = None
    phong_ngu: int | None = None
    toa_do_x: float
    toa_do_y: float
    so_tang: int | None = None


class PredictOutput(BaseModel):
    predicted_price_per_m2: float
    predicted_total_price: float


class TrainingRunSchema(BaseModel):
    id: int
    triggered_at: datetime
    status: str
    new_rows: int | None = None
    total_rows: int | None = None
    duration_sec: float | None = None
    model_replaced: bool | None = None

    model_config = {"from_attributes": True}


class MetricsTrendItem(BaseModel):
    run_id: int
    date: datetime
    rmse: float
    mae: float
    r2: float
