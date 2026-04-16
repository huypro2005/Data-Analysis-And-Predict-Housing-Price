"""
Integration tests cho /retrain/* endpoints
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.db.models import ModelMetrics, TrainingRun


class TestTriggerRetrain:
    def test_returns_200_when_idle(self, client):
        """Không có run đang chạy → 200."""
        with patch("app.api.api_retrain.do_retrain"):
            response = client.post("/retrain/trigger")
        assert response.status_code == 200
        assert "kích hoạt" in response.json()["message"].lower()

    def test_returns_409_when_already_running(self, client, db_session):
        """Đã có run status=running → 409."""
        run = TrainingRun(status="running", triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        response = client.post("/retrain/trigger")
        assert response.status_code == 409
        assert str(run.id) in response.json()["detail"]

    def test_background_task_registered(self, client):
        """Background task phải được thêm vào (không throw)."""
        called = []
        def fake_retrain(path):
            called.append(path)

        with patch("app.api.api_retrain.do_retrain", side_effect=fake_retrain):
            client.post("/retrain/trigger")
        # BackgroundTask chạy synchronously trong TestClient
        assert len(called) == 1


class TestRetainStatus:
    def test_idle_when_no_runs(self, client):
        """Không có run nào → status = 'idle', last_run = null."""
        response = client.get("/retrain/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["last_run"] is None

    def test_idle_when_last_run_success(self, client, training_run_success):
        """Run gần nhất là success → status = 'idle'."""
        data = client.get("/retrain/status").json()
        assert data["status"] == "idle"

    def test_running_when_active_run(self, client, db_session):
        """Run đang chạy → status = 'running'."""
        run = TrainingRun(status="running", triggered_at=datetime.now(timezone.utc))
        db_session.add(run)
        db_session.commit()

        data = client.get("/retrain/status").json()
        assert data["status"] == "running"

    def test_last_run_contains_correct_fields(self, client, training_run_success):
        """last_run phải có đủ fields."""
        data = client.get("/retrain/status").json()
        last = data["last_run"]
        for field in ["id", "triggered_at", "status", "new_rows", "model_replaced"]:
            assert field in last

    def test_last_run_id_matches(self, client, training_run_success):
        data = client.get("/retrain/status").json()
        assert data["last_run"]["id"] == training_run_success.id


class TestRetainHistory:
    def test_empty_history(self, client):
        """Không có run → items rỗng."""
        data = client.get("/retrain/history").json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_returns_runs_with_metrics(self, client, training_run_success):
        """Trả về runs có kèm metrics."""
        data = client.get("/retrain/history").json()
        assert data["total"] >= 1
        item = data["items"][0]
        assert item["metrics"] is not None
        assert "rmse" in item["metrics"]

    def test_pagination_page_size(self, client, db_session):
        """Phân trang: size=2 → trả về tối đa 2 item."""
        for i in range(5):
            run = TrainingRun(
                status="success",
                triggered_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                total_rows=100 + i * 10,
            )
            db_session.add(run)
        db_session.commit()

        data = client.get("/retrain/history?page=1&size=2").json()
        assert len(data["items"]) == 2

    def test_pagination_total_count(self, client, db_session):
        """total phải phản ánh số run thực tế."""
        for _ in range(3):
            db_session.add(TrainingRun(status="success", triggered_at=datetime.now(timezone.utc)))
        db_session.commit()

        data = client.get("/retrain/history?page=1&size=10").json()
        assert data["total"] >= 3

    def test_ordered_by_triggered_at_desc(self, client, db_session):
        """Runs phải được sắp xếp mới nhất trước."""
        run1 = TrainingRun(status="success", triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        run2 = TrainingRun(status="success", triggered_at=datetime(2026, 3, 1, tzinfo=timezone.utc))
        db_session.add_all([run1, run2])
        db_session.commit()

        data = client.get("/retrain/history").json()
        ids = [item["id"] for item in data["items"]]
        assert ids.index(run2.id) < ids.index(run1.id)


class TestMetricsTrend:
    def test_empty_when_no_success_runs(self, client):
        """Không có run success → runs rỗng."""
        data = client.get("/retrain/metrics/trend").json()
        assert data["runs"] == []

    def test_only_success_runs_included(self, client, db_session):
        """Chỉ run status='success' mới được đưa vào trend."""
        failed = TrainingRun(status="failed", triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        skipped = TrainingRun(status="skipped", triggered_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        success = TrainingRun(status="success", triggered_at=datetime(2026, 1, 3, tzinfo=timezone.utc))
        db_session.add_all([failed, skipped, success])
        db_session.flush()
        db_session.add(ModelMetrics(run_id=success.id, rmse=0.25, mae=0.18, r2=0.88))
        db_session.commit()

        data = client.get("/retrain/metrics/trend").json()
        run_ids = [r["run_id"] for r in data["runs"]]
        assert success.id in run_ids
        assert failed.id not in run_ids
        assert skipped.id not in run_ids

    def test_trend_item_has_required_fields(self, client, training_run_success):
        data = client.get("/retrain/metrics/trend").json()
        assert len(data["runs"]) >= 1
        item = data["runs"][0]
        for field in ["run_id", "date", "rmse", "mae", "r2"]:
            assert field in item
