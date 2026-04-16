"""
Shared fixtures cho toàn bộ test suite.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.db import models  # noqa: F401 — đảm bảo models được đăng ký


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """In-memory SQLite engine, dùng chung cho cả session test."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Mỗi test nhận 1 session riêng, wrap trong transaction.
    Rollback sau khi test xong → DB sạch giữa các test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client(db_session):
    """
    TestClient với get_db bị override bằng test session.
    Không dùng main.py (bỏ qua APScheduler).
    """
    from app.api import api_router

    app = FastAPI()
    app.include_router(api_router.router)
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# DB record helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def training_run_success(db_session):
    """TrainingRun thành công với đầy đủ relationships."""
    run = models.TrainingRun(
        status="success",
        triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        total_rows=1000,
        new_rows=200,
        duration_sec=120.0,
        model_replaced=True,
    )
    db_session.add(run)
    db_session.flush()

    metrics = models.ModelMetrics(
        run_id=run.id, rmse=0.25, mae=0.18, r2=0.88,
        prev_rmse=0.30, prev_mae=0.22, prev_r2=0.84,
    )
    db_session.add(metrics)

    for feat, imp in [("cách trung tâm", 0.31), ("diện tích", 0.25), ("địa chỉ", 0.15)]:
        db_session.add(models.FeatureImportance(run_id=run.id, feature_name=feat, importance=imp))

    for label, min_r, max_r, cnt in [
        ("0-30", 0, 30, 50), ("30-50", 30, 50, 120), ("50-70", 50, 70, 200),
        ("70-90", 70, 90, 180), ("90-110", 90, 110, 100),
        ("110-130", 110, 130, 60), ("130+", 130, float("inf"), 40),
    ]:
        db_session.add(models.PriceDistribution(
            run_id=run.id, price_range=label, min_range=min_r, max_range=max_r, samples_count=cnt,
        ))

    for dc, pc, mp, sc in [(18, 2, 85.0, 50), (18, 0, 55.0, 80), (9, 4, 200.0, 30)]:
        db_session.add(models.DistrictPriceStats(
            run_id=run.id, district_code=dc, property_code=pc, median_price=mp, sample_count=sc,
        ))

    db_session.commit()
    return run


@pytest.fixture()
def active_path_activation(db_session, training_run_success, tmp_path):
    """PathActivation is_active=True, với scatter file thực trên disk."""
    # Tạo scatter file thực để test FileResponse
    scatter_file = tmp_path / "scatter_test.csv"
    scatter_file.write_text("toa_do_x,toa_do_y,dien_tich,gia_m2\n10.7,106.7,80,55\n")

    activation = models.PathActivation(
        run_id=training_run_success.id,
        path_model="media/model_ai/rf_test.pkl",
        path_scatter=str(scatter_file),      # dùng absolute path cho test
        path_data="data/data.csv",
        is_active=True,
    )
    db_session.add(activation)
    db_session.commit()
    return activation
