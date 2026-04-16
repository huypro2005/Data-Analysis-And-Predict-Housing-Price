"""
Integration tests cho POST /predict
"""
import numpy as np
import pytest
from unittest.mock import patch

from test.helpers import PREDICT_PAYLOAD, make_mock_pipeline


class TestPredictEndpoint:
    # ------------------------------------------------------------------
    # Khi không có model active
    # ------------------------------------------------------------------

    def test_returns_null_when_no_active_model(self, client):
        """Chưa có PathActivation → predicted_price_per_m2 = null."""
        response = client.post("/predict", json=PREDICT_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["predicted_price_per_m2"] is None

    # ------------------------------------------------------------------
    # Khi có model active
    # ------------------------------------------------------------------

    def test_returns_200_with_active_model(self, client, active_path_activation):
        mock_pl = make_mock_pipeline(predict_log_value=3.8)
        with patch("app.service.predict_service.jb.load", return_value=mock_pl):
            response = client.post("/predict", json=PREDICT_PAYLOAD)
        assert response.status_code == 200

    def test_response_has_required_fields(self, client, active_path_activation):
        mock_pl = make_mock_pipeline()
        with patch("app.service.predict_service.jb.load", return_value=mock_pl):
            data = client.post("/predict", json=PREDICT_PAYLOAD).json()
        assert "predicted_price_per_m2" in data
        assert "predicted_total_price" in data

    def test_price_per_m2_is_positive(self, client, active_path_activation):
        mock_pl = make_mock_pipeline(predict_log_value=3.8)
        with patch("app.service.predict_service.jb.load", return_value=mock_pl):
            data = client.post("/predict", json=PREDICT_PAYLOAD).json()
        assert data["predicted_price_per_m2"] > 0

    def test_total_price_equals_price_times_area(self, client, active_path_activation):
        mock_pl = make_mock_pipeline(predict_log_value=4.0)
        payload = {**PREDICT_PAYLOAD, "diện tích": 100.0}
        with patch("app.service.predict_service.jb.load", return_value=mock_pl):
            data = client.post("/predict", json=payload).json()
        expected_total = data["predicted_price_per_m2"] * 100.0
        assert data["predicted_total_price"] == pytest.approx(expected_total, rel=1e-5)

    def test_price_is_exp_of_log_prediction(self, client, active_path_activation):
        log_val = 3.9
        mock_pl = make_mock_pipeline(predict_log_value=log_val)
        with patch("app.service.predict_service.jb.load", return_value=mock_pl):
            data = client.post("/predict", json=PREDICT_PAYLOAD).json()
        assert data["predicted_price_per_m2"] == pytest.approx(np.exp(log_val), rel=1e-4)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_optional_fields_can_be_null(self, client, active_path_activation):
        """mặt tiền, phòng ngủ, số tầng đều null → vẫn OK."""
        payload = {
            "loại nhà đất": 2, "địa chỉ": 18, "diện tích": 80.0,
            "mặt tiền": None, "phòng ngủ": None,
            "tọa độ x": 10.73, "tọa độ y": 106.72, "số tầng": None,
        }
        mock_pl = make_mock_pipeline()
        with patch("app.service.predict_service.jb.load", return_value=mock_pl):
            response = client.post("/predict", json=payload)
        assert response.status_code == 200
        assert response.json()["predicted_price_per_m2"] is not None

    def test_different_property_types(self, client, active_path_activation):
        """Các loại BĐS khác nhau đều được xử lý."""
        mock_pl = make_mock_pipeline()
        for loai in [0, 2, 3, 4, 7]:
            payload = {**PREDICT_PAYLOAD, "loại nhà đất": loai}
            with patch("app.service.predict_service.jb.load", return_value=mock_pl):
                response = client.post("/predict", json=payload)
            assert response.status_code == 200
