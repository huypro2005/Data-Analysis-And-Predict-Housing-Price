"""
Unit tests cho app/service/predict_service.py
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from app.service.predict_service import haversine, handle_input, predict, HCM_LAT, HCM_LON, X_TRAIN_COLUMNS


# ---------------------------------------------------------------------------
# haversine
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_returns_zero(self):
        """Khoảng cách từ điểm đến chính nó phải là 0."""
        assert haversine(HCM_LAT, HCM_LON) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_quan7(self):
        """Quận 7 (10.732, 106.721) cách trung tâm ~5-6 km."""
        d = haversine(10.732, 106.721)
        assert 4.0 < d < 8.0

    def test_custom_reference_point(self):
        """Cho phép truyền điểm tham chiếu khác."""
        d1 = haversine(10.73, 106.70, lat2=10.73, lon2=106.70)
        assert d1 == pytest.approx(0.0, abs=1e-6)

    def test_returns_float(self):
        d = haversine(10.8, 106.6)
        assert isinstance(float(d), float)

    def test_symmetry(self):
        """haversine(A→B) == haversine(B→A)."""
        d1 = haversine(10.73, 106.72, lat2=10.78, lon2=106.70)
        d2 = haversine(10.78, 106.70, lat2=10.73, lon2=106.72)
        assert d1 == pytest.approx(d2, rel=1e-9)


# ---------------------------------------------------------------------------
# handle_input
# ---------------------------------------------------------------------------

class TestHandleInput:
    @pytest.fixture()
    def median_series(self):
        return pd.Series(
            [2.0, 18.0, 80.0, 5.0, 2.0, 10.75, 106.68, 2.0, 8.0],
            index=X_TRAIN_COLUMNS,
        )

    def test_returns_dataframe(self, median_series):
        data = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": 5.0, "phòng ngủ": 2,
            "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": 3,
        }
        result = handle_input(data, median_series)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_contains_distance_column(self, median_series):
        data = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": None, "phòng ngủ": None,
            "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None,
        }
        result = handle_input(data, median_series)
        assert "cách trung tâm" in result.columns

    def test_none_filled_with_median(self, median_series):
        data = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": None, "phòng ngủ": None,
            "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None,
        }
        result = handle_input(data, median_series)
        assert not result["mặt tiền"].isna().any()
        assert not result["phòng ngủ"].isna().any()
        assert not result["số tầng"].isna().any()

    def test_provided_values_not_overwritten(self, median_series):
        data = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": 7.5, "phòng ngủ": 3,
            "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": 4,
        }
        result = handle_input(data, median_series)
        assert result["mặt tiền"].iloc[0] == pytest.approx(7.5)
        assert int(result["phòng ngủ"].iloc[0]) == 3
        assert int(result["số tầng"].iloc[0]) == 4

    def test_distance_is_positive(self, median_series):
        data = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": None, "phòng ngủ": None,
            "tọa độ x": 10.73, "toa_do_y": 106.72, "tọa độ y": 106.72, "số tầng": None,
        }
        result = handle_input(data, median_series)
        assert result["cách trung tâm"].iloc[0] > 0

    def test_all_columns_present(self, median_series):
        data = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": None, "phòng ngủ": None,
            "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None,
        }
        result = handle_input(data, median_series)
        for col in X_TRAIN_COLUMNS:
            assert col in result.columns, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------

class TestPredict:
    def test_returns_none_when_no_active_model(self, db_session):
        """Không có PathActivation → trả về (None, None)."""
        price, total = predict({"loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
                                 "mặt tiền": None, "phòng ngủ": None,
                                 "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None},
                                db_session=db_session)
        assert price is None
        assert total is None

    def test_returns_floats_with_active_model(self, db_session, active_path_activation):
        """Khi có PathActivation + pipeline hợp lệ → trả về float."""
        from test.helpers import make_mock_pipeline
        mock_pipeline = make_mock_pipeline(predict_log_value=3.8)

        with patch("app.service.predict_service.jb.load", return_value=mock_pipeline):
            price, total = predict(
                {"loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
                 "mặt tiền": None, "phòng ngủ": None,
                 "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None},
                db_session=db_session,
            )

        assert price is not None
        assert total is not None
        assert isinstance(price, float)
        assert isinstance(total, float)

    def test_price_is_exp_of_log_prediction(self, db_session, active_path_activation):
        """Giá = exp(log_prediction) ~ đúng."""
        log_val = 3.8
        from test.helpers import make_mock_pipeline
        mock_pipeline = make_mock_pipeline(predict_log_value=log_val)

        with patch("app.service.predict_service.jb.load", return_value=mock_pipeline):
            price, _ = predict(
                {"loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
                 "mặt tiền": 5.0, "phòng ngủ": 2,
                 "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": 3},
                db_session=db_session,
            )

        assert price == pytest.approx(np.exp(log_val), rel=1e-5)

    def test_total_price_equals_price_times_area(self, db_session, active_path_activation):
        """Total price = price_per_m2 × diện tích."""
        from test.helpers import make_mock_pipeline
        mock_pipeline = make_mock_pipeline(predict_log_value=4.0)

        with patch("app.service.predict_service.jb.load", return_value=mock_pipeline):
            price, total = predict(
                {"loại nhà đất": 2, "địa chỉ": 18, "diện tích": 100.0,
                 "mặt tiền": None, "phòng ngủ": None,
                 "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None},
                db_session=db_session,
            )

        assert total == pytest.approx(price * 100.0, rel=1e-5)

    def test_returns_none_on_exception(self, db_session, active_path_activation):
        """Exception bên trong → trả về (None, None)."""
        with patch("app.service.predict_service.jb.load", side_effect=RuntimeError("broken")):
            price, total = predict(
                {"loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
                 "mặt tiền": None, "phòng ngủ": None,
                 "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None},
                db_session=db_session,
            )
        assert price is None
        assert total is None
