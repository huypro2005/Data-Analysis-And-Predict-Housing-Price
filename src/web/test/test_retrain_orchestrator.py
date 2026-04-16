"""
Unit tests cho RetrainOrchestrator (app/retrain/retrain_service.py)
"""
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.db.models import PathActivation, TrainingRun, ModelMetrics
from app.retrain.retrain_service import RetrainOrchestrator
from test.helpers import make_valid_csv_df


def _make_retrain_result(rmse: float = 0.25) -> dict:
    """Tạo kết quả giả từ RetrainService.retrain_model()."""
    pipeline_mock = MagicMock()
    return {
        "pipeline": pipeline_mock,
        "importance": pd.Series(
            {"cách trung tâm": 0.31, "diện tích": 0.25, "địa chỉ": 0.15,
             "loại nhà đất": 0.10, "mặt tiền": 0.08, "phòng ngủ": 0.05,
             "tọa độ x": 0.03, "tọa độ y": 0.02, "số tầng": 0.01}
        ),
        "data_price_distribution": {
            "0-30": 50, "30-50": 120, "50-70": 200,
            "70-90": 180, "90-110": 100, "110-130": 60, "130+": 40,
        },
        "data_scatter_plot": pd.DataFrame({
            "tọa độ x": [10.73] * 50,
            "tọa độ y": [106.72] * 50,
            "diện tích": [80.0] * 50,
            "giá/m2": [55.0] * 50,
        }),
        "data_district_stats": pd.DataFrame({
            "district_code": [18, 18, 9],
            "property_code": [2, 0, 4],
            "median_price": [85.0, 55.0, 200.0],
            "sample_count": [50, 80, 30],
        }),
        "rmse": rmse,
        "mae": 0.18,
        "r2": 0.88,
    }


# ---------------------------------------------------------------------------
# check_new_rows
# ---------------------------------------------------------------------------

class TestCheckNewRows:
    def test_returns_total_when_no_previous_run(self, db_session, tmp_path):
        """Chưa có run nào → trả về tổng số dòng."""
        df = make_valid_csv_df(150)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        orch = RetrainOrchestrator(db_session)
        assert orch.check_new_rows(path) == 150

    def test_returns_diff_since_last_run(self, db_session, tmp_path):
        """Có run trước với 100 dòng, data hiện tại 150 → diff = 50."""
        run = TrainingRun(status="success", total_rows=100, triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        df = make_valid_csv_df(150)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        orch = RetrainOrchestrator(db_session)
        assert orch.check_new_rows(path) == 50

    def test_returns_zero_when_no_new_data(self, db_session, tmp_path):
        """Data không đổi → diff = 0."""
        run = TrainingRun(status="success", total_rows=150, triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        df = make_valid_csv_df(150)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        orch = RetrainOrchestrator(db_session)
        assert orch.check_new_rows(path) == 0

    def test_ignores_failed_runs(self, db_session, tmp_path):
        """Run failed không được tính là run thành công cuối cùng."""
        run = TrainingRun(status="failed", total_rows=None, triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        df = make_valid_csv_df(150)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        # Không có run success → trả về tổng
        orch = RetrainOrchestrator(db_session)
        assert orch.check_new_rows(path) == 150


# ---------------------------------------------------------------------------
# run() — skip case
# ---------------------------------------------------------------------------

class TestOrchestratorRunSkip:
    def test_skips_when_few_new_rows(self, db_session, tmp_path):
        """< 100 dòng mới → status='skipped'."""
        # Run cũ với 200 dòng
        run = TrainingRun(status="success", total_rows=200, triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        # Data mới chỉ có 250 (chênh 50, < 100)
        df = make_valid_csv_df(250)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        orch = RetrainOrchestrator(db_session)
        result = orch.run(path)

        assert result["status"] == "skipped"
        assert result["new_rows"] == 50

    def test_skip_saves_training_run_to_db(self, db_session, tmp_path):
        """Khi skip, phải lưu TrainingRun vào DB."""
        run = TrainingRun(status="success", total_rows=200, triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        df = make_valid_csv_df(250)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        orch = RetrainOrchestrator(db_session)
        orch.run(path)

        skipped_run = (db_session.query(TrainingRun)
                       .filter(TrainingRun.status == "skipped")
                       .first())
        assert skipped_run is not None
        assert skipped_run.skip_reason is not None


# ---------------------------------------------------------------------------
# run() — success case (mock RetrainService)
# ---------------------------------------------------------------------------

class TestOrchestratorRunSuccess:
    def test_success_first_run_always_replaces(self, db_session, tmp_path):
        """Lần retrain đầu tiên (không có model cũ) → luôn replace."""
        df = make_valid_csv_df(300)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        result_data = _make_retrain_result(rmse=0.25)

        with patch("app.retrain.retrain_service.RetrainService") as MockSvc, \
             patch("app.retrain.retrain_service.jb.dump"):
            MockSvc.return_value.retrain_model.return_value = result_data
            orch = RetrainOrchestrator(db_session)
            result = orch.run(path)

        assert result["status"] == "success"
        assert result["model_replaced"] is True

    def test_success_saves_metrics_to_db(self, db_session, tmp_path):
        """Sau retrain thành công, ModelMetrics phải được lưu vào DB."""
        df = make_valid_csv_df(300)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        result_data = _make_retrain_result(rmse=0.25)

        with patch("app.retrain.retrain_service.RetrainService") as MockSvc, \
             patch("app.retrain.retrain_service.jb.dump"):
            MockSvc.return_value.retrain_model.return_value = result_data
            orch = RetrainOrchestrator(db_session)
            result = orch.run(path)

        metrics = db_session.query(ModelMetrics).filter(ModelMetrics.run_id == result["run_id"]).first()
        assert metrics is not None
        assert metrics.rmse == pytest.approx(0.25, rel=1e-5)

    def test_success_creates_path_activation(self, db_session, tmp_path):
        """PathActivation is_active=True phải được tạo."""
        df = make_valid_csv_df(300)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        result_data = _make_retrain_result(rmse=0.25)

        with patch("app.retrain.retrain_service.RetrainService") as MockSvc, \
             patch("app.retrain.retrain_service.jb.dump"):
            MockSvc.return_value.retrain_model.return_value = result_data
            orch = RetrainOrchestrator(db_session)
            result = orch.run(path)

        activation = (db_session.query(PathActivation)
                      .filter(PathActivation.is_active == True)  # noqa: E712
                      .first())
        assert activation is not None
        assert activation.run_id == result["run_id"]

    def test_only_one_active_path_activation(self, db_session, tmp_path):
        """Chỉ được có đúng 1 record is_active=True."""
        df = make_valid_csv_df(300)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        result_data = _make_retrain_result(rmse=0.25)

        # Retrain lần 1
        with patch("app.retrain.retrain_service.RetrainService") as MockSvc, \
             patch("app.retrain.retrain_service.jb.dump"), \
             patch("app.retrain.retrain_service.jb.load", return_value=MagicMock()):
            MockSvc.return_value.retrain_model.return_value = result_data
            orch = RetrainOrchestrator(db_session)
            orch.run(path)

        # Retrain lần 2 (RMSE tốt hơn)
        df2 = make_valid_csv_df(500)
        path2 = str(tmp_path / "data2.csv")
        df2.to_csv(path2, index=False)
        result_data2 = _make_retrain_result(rmse=0.20)

        with patch("app.retrain.retrain_service.RetrainService") as MockSvc, \
             patch("app.retrain.retrain_service.jb.dump"), \
             patch("app.retrain.retrain_service.jb.load", return_value=MagicMock()):
            MockSvc.return_value.retrain_model.return_value = result_data2
            orch = RetrainOrchestrator(db_session)
            orch.run(path2)

        active_count = (db_session.query(PathActivation)
                        .filter(PathActivation.is_active == True)  # noqa: E712
                        .count())
        assert active_count == 1

    def test_does_not_replace_when_rmse_worse(self, db_session, tmp_path, training_run_success, active_path_activation):
        """RMSE mới tệ hơn → không replace model."""
        df = make_valid_csv_df(300)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        # RMSE mới = 0.50, cũ = 0.25 (worse)
        result_data = _make_retrain_result(rmse=0.50)

        mock_old_metrics = MagicMock()
        mock_old_metrics.rmse = 0.25

        with patch("app.retrain.retrain_service.RetrainService") as MockSvc, \
             patch("app.retrain.retrain_service.jb.load", return_value=MagicMock()), \
             patch("app.retrain.retrain_service.jb.dump"):
            MockSvc.return_value.retrain_model.return_value = result_data
            # Mock activation.run.metrics
            active_path_activation.run.metrics = mock_old_metrics
            orch = RetrainOrchestrator(db_session)
            result = orch.run(path)

        assert result["model_replaced"] is False


# ---------------------------------------------------------------------------
# run() — failure case
# ---------------------------------------------------------------------------

class TestOrchestratorRunFailure:
    def test_marks_failed_on_exception(self, db_session, tmp_path):
        """Exception trong retrain_model → TrainingRun status='failed'."""
        df = make_valid_csv_df(300)
        path = str(tmp_path / "data.csv")
        df.to_csv(path, index=False)

        with patch("app.retrain.retrain_service.RetrainService") as MockSvc:
            MockSvc.return_value.retrain_model.side_effect = RuntimeError("Train failed")
            orch = RetrainOrchestrator(db_session)
            with pytest.raises(RuntimeError):
                orch.run(path)

        failed_run = (db_session.query(TrainingRun)
                      .filter(TrainingRun.status == "failed")
                      .first())
        assert failed_run is not None
