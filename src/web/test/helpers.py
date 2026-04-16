"""
Shared helpers cho test suite.
"""
import numpy as np
import pandas as pd


def make_valid_csv_df(n: int = 200, property_type: int = 2, district: int = 18) -> pd.DataFrame:
    """
    Tạo DataFrame tổng hợp hợp lệ cho RetrainService.
    - Tọa độ x/y ở dạng ×1e9 (như trong data.csv thực)
    - Tất cả giá trị vượt qua các bộ lọc preprocessing
    """
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "loại nhà đất": [property_type] * n,
        "địa chỉ":      [district] * n,
        "diện tích":    rng.uniform(50, 200, n),
        "mặt tiền":     rng.uniform(3, 10, n),
        "phòng ngủ":    rng.integers(1, 5, n).astype(float),
        "tọa độ x":     rng.uniform(10.50, 10.80, n) * 1e9,   # ×1e9
        "tọa độ y":     rng.uniform(106.50, 106.75, n) * 1e9, # ×1e9
        "số tầng":      rng.integers(1, 4, n).astype(float),
        "pháp lý":      rng.choice([0.0, 1.0], n),
        "giá/m2":       rng.uniform(30, 200, n),
        "giá":          rng.uniform(1_000, 50_000, n),
    })


def make_mock_pipeline(predict_log_value: float = 3.8):
    """
    Tạo mock sklearn Pipeline giống interface thực.
    predict_log_value → exp(3.8) ≈ 44.7 triệu/m²
    """
    from unittest.mock import MagicMock
    import numpy as np

    X_COLS = [
        "loại nhà đất", "địa chỉ", "diện tích", "mặt tiền",
        "phòng ngủ", "tọa độ x", "tọa độ y", "số tầng", "cách trung tâm",
    ]
    median_vals = np.array([2.0, 18.0, 80.0, 5.0, 2.0, 10.75, 106.68, 2.0, 8.0])

    imputer_mock = MagicMock()
    imputer_mock.statistics_ = median_vals

    pipeline = MagicMock()
    pipeline.named_steps = {"imputer": imputer_mock, "model": MagicMock()}
    pipeline.predict.return_value = np.array([predict_log_value])
    return pipeline


PREDICT_PAYLOAD = {
    "loại nhà đất": 2,
    "địa chỉ": 18,
    "diện tích": 80.0,
    "mặt tiền": None,
    "phòng ngủ": 2,
    "tọa độ x": 10.73,
    "tọa độ y": 106.72,
    "số tầng": None,
}
