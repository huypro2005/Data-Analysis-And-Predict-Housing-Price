import joblib as jb
import numpy as np
import pandas as pd

from app.config import BASE_DIR
from app.db.database import SessionLocal
from app.db.models import PathActivation

# Tọa độ trung tâm TP.HCM (Nhà thờ Đức Bà)
HCM_LAT = 10.7769
HCM_LON = 106.7009

X_TRAIN_COLUMNS = [
    "loại nhà đất", "địa chỉ", "diện tích", "mặt tiền",
    "phòng ngủ", "tọa độ x", "tọa độ y", "số tầng", "cách trung tâm",
]


def haversine(lat1, lon1, lat2=HCM_LAT, lon2=HCM_LON):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def _load_active_pipeline(db_session=None):
    """
    Query PathActivation WHERE is_active=True, load pipeline từ path_model.
    Trả về (pipeline, median_series).
    """
    close_after = db_session is None
    if db_session is None:
        db_session = SessionLocal()

    try:
        activation = (
            db_session.query(PathActivation)
            .filter(PathActivation.is_active == True)  # noqa: E712
            .first()
        )
        if activation is None:
            return None, None

        model_abs = BASE_DIR / activation.path_model
        print(f"Loading model from {model_abs}...")
        pipeline = jb.load(str(model_abs))
        median = pipeline.named_steps["imputer"].statistics_
        median_series = pd.Series(median, index=X_TRAIN_COLUMNS)
        return pipeline, median_series
    finally:
        if close_after:
            db_session.close()


def handle_input(input_data: dict, median_series: pd.Series) -> pd.DataFrame:
    data = pd.DataFrame({
        "loại nhà đất": [int(input_data["loại nhà đất"])],
        "địa chỉ":      [int(input_data["địa chỉ"])],
        "diện tích":    [float(input_data["diện tích"])],
        "mặt tiền":     [float(input_data["mặt tiền"]) if input_data.get("mặt tiền") is not None else np.nan],
        "phòng ngủ":    [int(input_data["phòng ngủ"])  if input_data.get("phòng ngủ") is not None else np.nan],
        "tọa độ x":     [float(input_data["tọa độ x"])],
        "tọa độ y":     [float(input_data["tọa độ y"])],
        "số tầng":      [int(input_data["số tầng"])    if input_data.get("số tầng") is not None else np.nan],
    })
    data["cách trung tâm"] = haversine(data["tọa độ x"], data["tọa độ y"])
    data.fillna(median_series, inplace=True)
    return data


def predict(data: dict, db_session=None):
    try:
        pipeline, median_series = _load_active_pipeline(db_session)
        if pipeline is None:
            return None, None

        data_processed = handle_input(data, median_series)
        prediction_log = pipeline.predict(data_processed)
        price_per_m2 = float(np.exp(prediction_log)[0])
        total_price = float(price_per_m2 * data_processed["diện tích"].iloc[0])
        return price_per_m2, total_price
    except Exception as e:
        print(f"Predict error: {e}")
        return None, None
