"""
Unit tests cho DB models và Enums (app/db/models.py)
"""
import pytest
from datetime import datetime, timezone

from app.db.models import (
    District, RealEstateType, TrainingRun, ModelMetrics,
    FeatureImportance, PriceDistribution, DistrictPriceStats, PathActivation,
)


# ---------------------------------------------------------------------------
# District enum
# ---------------------------------------------------------------------------

class TestDistrictEnum:
    def test_all_24_districts_defined(self):
        assert len(list(District)) == 24

    def test_code_property(self):
        assert District.QUAN_7.code == 18
        assert District.QUAN_1.code == 9
        assert District.BINH_CHANH.code == 0

    def test_label_property(self):
        assert District.QUAN_7.label == "quận 7"
        assert District.THU_DUC.label == "thủ đức"

    def test_from_code(self):
        assert District.from_code(18) == District.QUAN_7

    def test_from_code_invalid_raises(self):
        with pytest.raises(ValueError):
            District.from_code(999)

    def test_from_label(self):
        assert District.from_label("quận 7") == District.QUAN_7

    def test_from_label_case_insensitive(self):
        assert District.from_label("QUẬN 7") == District.QUAN_7

    def test_from_label_invalid_raises(self):
        with pytest.raises(ValueError):
            District.from_label("đà nẵng")

    @pytest.mark.parametrize("code,expected_label", [
        (0, "bình chánh"), (1, "bình tân"), (9, "quận 1"),
        (21, "thủ đức"), (23, "tân phú"),
    ])
    def test_all_codes_map_correctly(self, code, expected_label):
        assert District.from_code(code).label == expected_label


# ---------------------------------------------------------------------------
# RealEstateType enum
# ---------------------------------------------------------------------------

class TestRealEstateTypeEnum:
    def test_5_types_defined(self):
        assert len(list(RealEstateType)) == 5

    def test_codes_are_correct(self):
        assert RealEstateType.CAN_HO_CHUNG_CU.code == 0
        assert RealEstateType.NHA_RIENG.code == 2
        assert RealEstateType.NHA_BIET_THU.code == 3
        assert RealEstateType.NHA_MAT_PHO.code == 4
        assert RealEstateType.BAN_DAT.code == 7

    def test_labels_are_correct(self):
        assert RealEstateType.NHA_RIENG.label == "nhà riêng"
        assert RealEstateType.BAN_DAT.label == "bán đất"

    def test_from_code(self):
        assert RealEstateType.from_code(2) == RealEstateType.NHA_RIENG

    def test_from_code_invalid_raises(self):
        with pytest.raises(ValueError):
            RealEstateType.from_code(1)   # code 1 bị loại

    def test_from_label(self):
        assert RealEstateType.from_label("nhà riêng") == RealEstateType.NHA_RIENG

    def test_from_label_strips_whitespace(self):
        assert RealEstateType.from_label("  nhà riêng  ") == RealEstateType.NHA_RIENG


# ---------------------------------------------------------------------------
# ORM model creation & relationships
# ---------------------------------------------------------------------------

class TestOrmModels:
    def test_training_run_default_triggered_at(self, db_session):
        """triggered_at phải được tự động set."""
        run = TrainingRun(status="running")
        db_session.add(run)
        db_session.commit()
        assert run.triggered_at is not None

    def test_training_run_relationships(self, db_session, training_run_success):
        """Relationship metrics, feature_importances phải hoạt động."""
        db_session.refresh(training_run_success)
        assert training_run_success.metrics is not None
        assert len(training_run_success.feature_importances) == 3
        assert len(training_run_success.price_distributions) == 7
        assert len(training_run_success.district_price_stats) == 3

    def test_model_metrics_run_relationship(self, db_session, training_run_success):
        metrics = training_run_success.metrics
        assert metrics.run_id == training_run_success.id

    def test_district_price_stats_district_property(self, db_session, training_run_success):
        """district và real_estate_type properties phải trả về enum đúng."""
        stat = next(
            s for s in training_run_success.district_price_stats
            if s.district_code == 18
        )
        assert stat.district == District.QUAN_7
        assert stat.real_estate_type == RealEstateType.NHA_RIENG

    def test_path_activation_is_active(self, db_session, active_path_activation):
        assert active_path_activation.is_active is True

    def test_only_one_active_activation_enforced(self, db_session, training_run_success):
        """Nếu deactivate rồi tạo mới, chỉ còn 1 is_active=True."""
        # Activation 1
        a1 = PathActivation(
            run_id=training_run_success.id,
            path_model="m1.pkl", path_scatter="s1.csv", path_data="d1.csv",
            is_active=True,
        )
        db_session.add(a1)
        db_session.flush()

        # Deactivate và thêm activation 2
        a1.is_active = False
        run2 = TrainingRun(status="success")
        db_session.add(run2)
        db_session.flush()
        metrics2 = ModelMetrics(run_id=run2.id, rmse=0.2, mae=0.15, r2=0.9)
        db_session.add(metrics2)
        a2 = PathActivation(
            run_id=run2.id,
            path_model="m2.pkl", path_scatter="s2.csv", path_data="d2.csv",
            is_active=True,
        )
        db_session.add(a2)
        db_session.commit()

        active_count = (db_session.query(PathActivation)
                        .filter(PathActivation.is_active == True)  # noqa: E712
                        .count())
        assert active_count == 1
        assert db_session.query(PathActivation).filter(
            PathActivation.is_active == True  # noqa: E712
        ).first().id == a2.id
