"""
Integration tests cho GET /feature-importance
"""
import pytest


class TestFeatureImportance:
    def test_404_when_no_active_model(self, client):
        """Chưa có model active → 404."""
        assert client.get("/feature-importance").status_code == 404

    def test_returns_run_id(self, client, active_path_activation):
        data = client.get("/feature-importance").json()
        assert data["run_id"] == active_path_activation.run_id

    def test_returns_features_list(self, client, active_path_activation):
        data = client.get("/feature-importance").json()
        assert isinstance(data["features"], list)
        assert len(data["features"]) > 0

    def test_feature_has_required_fields(self, client, active_path_activation):
        data = client.get("/feature-importance").json()
        for feat in data["features"]:
            assert "name" in feat
            assert "importance" in feat

    def test_sorted_descending_by_importance(self, client, active_path_activation):
        """Phải được sắp xếp importance giảm dần."""
        data = client.get("/feature-importance").json()
        importances = [f["importance"] for f in data["features"]]
        assert importances == sorted(importances, reverse=True)

    def test_importance_values_non_negative(self, client, active_path_activation):
        data = client.get("/feature-importance").json()
        for feat in data["features"]:
            assert feat["importance"] >= 0

    def test_feature_names_are_strings(self, client, active_path_activation):
        data = client.get("/feature-importance").json()
        for feat in data["features"]:
            assert isinstance(feat["name"], str)
            assert feat["name"] != ""

    def test_top_feature_is_cach_trung_tam(self, client, active_path_activation):
        """Feature quan trọng nhất trong fixture là 'cách trung tâm'."""
        data = client.get("/feature-importance").json()
        assert data["features"][0]["name"] == "cách trung tâm"
