"""
Unit tests cho app/retrain/retrain.py (RetrainService)
"""
import io
import math

import numpy as np
import pandas as pd
import pytest

from test.helpers import make_valid_csv_df


def _write_csv(df: pd.DataFrame, path) -> str:
    """Ghi DataFrame ra file CSV tạm, trả về path."""
    p = str(path / "data.csv")
    df.to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# RetrainService.__init__
# ---------------------------------------------------------------------------

class TestRetrainServiceInit:
    def test_normalizes_coordinates(self, tmp_path, db_session):
        """tọa độ x/y phải được chia /1e9 trong __init__."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(100)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        # Sau khi chia, giá trị phải nằm trong khoảng thực tế (~10-11, ~106-107)
        assert svc.df["tọa độ x"].between(10.0, 12.0).all()
        assert svc.df["tọa độ y"].between(105.0, 108.0).all()

    def test_drops_gia_column(self, tmp_path, db_session):
        """Cột 'giá' phải bị xóa để tránh data leakage."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(100)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        assert "giá" not in svc.df.columns

    def test_adds_cach_trung_tam(self, tmp_path, db_session):
        """Cột 'cách trung tâm' phải được thêm vào."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(100)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        assert "cách trung tâm" in svc.df.columns
        assert (svc.df["cách trung tâm"] >= 0).all()


# ---------------------------------------------------------------------------
# __compute_price_distribution
# ---------------------------------------------------------------------------

class TestPriceDistribution:
    def test_returns_all_7_bins(self, tmp_path, db_session):
        """Phải có đủ 7 bin."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        dist = svc._RetrainService__compute_price_distribution()
        assert set(dist.keys()) == {"0-30", "30-50", "50-70", "70-90", "90-110", "110-130", "130+"}

    def test_bin_counts_sum_to_total(self, tmp_path, db_session):
        """Tổng count phải bằng số dòng sau khi filter."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()  # áp filter trước
        dist = svc._RetrainService__compute_price_distribution()
        assert sum(dist.values()) == len(svc.df)

    def test_correct_bin_placement(self, tmp_path, db_session):
        """Giá 40 triệu/m² phải nằm trong bin '30-50'."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(50)
        df["giá/m2"] = 40.0  # tất cả rơi vào bin 30-50
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        dist = svc._RetrainService__compute_price_distribution()
        assert dist["30-50"] == len(svc.df)
        assert dist["0-30"] == 0


# ---------------------------------------------------------------------------
# __compute_district_stats
# ---------------------------------------------------------------------------

class TestDistrictStats:
    def test_filters_groups_below_10(self, tmp_path, db_session):
        """Nhóm < 10 mẫu phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200, district=18)
        # Thêm 5 dòng với quận khác (< 10 mẫu)
        small_group = make_valid_csv_df(5, district=3)
        df = pd.concat([df, small_group], ignore_index=True)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        stats = svc._RetrainService__compute_district_stats()
        assert (stats["sample_count"] >= 10).all()
        assert 3 not in stats["district_code"].values

    def test_returns_correct_columns(self, tmp_path, db_session):
        """DataFrame trả về phải có đủ cột."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        stats = svc._RetrainService__compute_district_stats()
        for col in ["district_code", "property_code", "median_price", "sample_count"]:
            assert col in stats.columns


# ---------------------------------------------------------------------------
# __preprocess_data — bộ lọc
# ---------------------------------------------------------------------------

class TestPreprocessFilters:
    def test_removes_unsupported_property_types(self, tmp_path, db_session):
        """Loại BĐS 1,5,6,8,9 phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200, property_type=2)
        # Thêm vài dòng với loại không hỗ trợ
        invalid = make_valid_csv_df(20, property_type=1)
        df = pd.concat([df, invalid], ignore_index=True)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert not svc.df["loại nhà đất"].isin({1, 5, 6, 8, 9}).any()

    def test_removes_coords_outside_hcm(self, tmp_path, db_session):
        """Tọa độ ngoài TP.HCM phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        # Thêm tọa độ ngoài Hà Nội
        outside = make_valid_csv_df(10)
        outside["tọa độ x"] = 21.0 * 1e9   # Hà Nội lat
        outside["tọa độ y"] = 105.8 * 1e9
        df = pd.concat([df, outside], ignore_index=True)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert svc.df["tọa độ x"].between(10.38, 11.10).all()

    def test_removes_invalid_legal_status(self, tmp_path, db_session):
        """Pháp lý == 2 và NaN phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        df.loc[0:9, "pháp lý"] = 2     # 10 dòng pháp lý không hợp lệ
        df.loc[10:14, "pháp lý"] = np.nan  # 5 dòng NaN
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert not (svc.df["pháp lý"] == 2).any()

    def test_removes_outlier_area(self, tmp_path, db_session):
        """Diện tích < 15 hoặc > 500 phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        df.loc[0, "diện tích"] = 5.0    # quá nhỏ
        df.loc[1, "diện tích"] = 600.0  # quá lớn
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert svc.df["diện tích"].between(15, 500).all()

    def test_removes_outlier_price(self, tmp_path, db_session):
        """Giá/m2 > 500 phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        df.loc[0, "giá/m2"] = 600.0
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert (svc.df["giá/m2"] <= 500).all()

    def test_removes_outlier_frontage(self, tmp_path, db_session):
        """Mặt tiền > 30 phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        df.loc[0, "mặt tiền"] = 50.0
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert (svc.df["mặt tiền"] <= 30).all()

    def test_removes_outlier_bedrooms(self, tmp_path, db_session):
        """Phòng ngủ >= 11 phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(200)
        df.loc[0, "phòng ngủ"] = 15.0
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        assert (svc.df["phòng ngủ"] < 11).all()

    def test_deduplication(self, tmp_path, db_session):
        """Dòng trùng lặp phải bị loại."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(100)
        df_dup = pd.concat([df, df.head(20)], ignore_index=True)  # 20 dòng trùng
        path = _write_csv(df_dup, tmp_path)
        svc = RetrainService(path, db_session)
        svc._RetrainService__preprocess_data()
        # Sau dedup + filter, số dòng phải <= len(df)
        assert len(svc.df) <= len(df)


# ---------------------------------------------------------------------------
# retrain_model
# ---------------------------------------------------------------------------

class TestRetrainModel:
    def test_returns_required_keys(self, tmp_path, db_session):
        """Kết quả phải có đủ các key."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(300)
        path = _write_csv(df, tmp_path)
        svc = RetrainService(path, db_session)
        result = svc.retrain_model()
        for key in ["pipeline", "importance", "data_price_distribution",
                    "data_scatter_plot", "data_district_stats", "rmse", "mae", "r2"]:
            assert key in result, f"Missing key: {key}"

    def test_r2_in_valid_range(self, tmp_path, db_session):
        """R² trên dữ liệu tổng hợp phải trong (-inf, 1]."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(300)
        path = _write_csv(df, tmp_path)
        result = RetrainService(path, db_session).retrain_model()
        assert result["r2"] <= 1.0

    def test_rmse_is_positive(self, tmp_path, db_session):
        """RMSE phải dương."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(300)
        path = _write_csv(df, tmp_path)
        result = RetrainService(path, db_session).retrain_model()
        assert result["rmse"] > 0

    def test_importance_sums_to_one(self, tmp_path, db_session):
        """Tổng feature importance phải xấp xỉ 1.0."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(300)
        path = _write_csv(df, tmp_path)
        result = RetrainService(path, db_session).retrain_model()
        assert result["importance"].sum() == pytest.approx(1.0, abs=1e-6)

    def test_scatter_plot_has_required_columns(self, tmp_path, db_session):
        """scatter DataFrame phải có 4 cột."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(300)
        path = _write_csv(df, tmp_path)
        result = RetrainService(path, db_session).retrain_model()
        scatter = result["data_scatter_plot"]
        assert set(scatter.columns) == {"tọa độ x", "tọa độ y", "diện tích", "giá/m2"}

    def test_pipeline_can_predict(self, tmp_path, db_session):
        """Pipeline trả về phải gọi predict() được."""
        from app.retrain.retrain import RetrainService
        df = make_valid_csv_df(300)
        path = _write_csv(df, tmp_path)
        result = RetrainService(path, db_session).retrain_model()
        pipeline = result["pipeline"]
        sample = df.drop(columns=["giá", "giá/m2", "pháp lý"]).head(1).copy()
        sample["tọa độ x"] /= 1e9
        sample["tọa độ y"] /= 1e9
        from app.retrain.retrain import haversine
        sample["cách trung tâm"] = haversine(sample["tọa độ x"], sample["tọa độ y"])
        pred = pipeline.predict(sample)
        assert len(pred) == 1
