"""
Integration tests cho /eda/* endpoints
"""
import pytest


class TestPriceDistribution:
    def test_404_when_no_active_model(self, client):
        """Chưa active → 404."""
        assert client.get("/eda/price-distribution").status_code == 404

    def test_returns_run_id(self, client, active_path_activation):
        data = client.get("/eda/price-distribution").json()
        assert data["run_id"] == active_path_activation.run_id

    def test_returns_7_bins(self, client, active_path_activation):
        data = client.get("/eda/price-distribution").json()
        assert len(data["bins"]) == 7

    def test_bin_labels_correct(self, client, active_path_activation):
        data = client.get("/eda/price-distribution").json()
        labels = {b["label"] for b in data["bins"]}
        expected = {"0-30", "30-50", "50-70", "70-90", "90-110", "110-130", "130+"}
        assert labels == expected

    def test_bin_has_required_fields(self, client, active_path_activation):
        data = client.get("/eda/price-distribution").json()
        for bin_item in data["bins"]:
            assert "label" in bin_item
            assert "min" in bin_item
            assert "max" in bin_item
            assert "count" in bin_item

    def test_counts_are_non_negative(self, client, active_path_activation):
        data = client.get("/eda/price-distribution").json()
        for bin_item in data["bins"]:
            assert bin_item["count"] >= 0


class TestDistrictPropertyType:
    def test_404_when_no_active_model(self, client):
        assert client.get("/eda/district-property-type").status_code == 404

    def test_returns_run_id(self, client, active_path_activation):
        data = client.get("/eda/district-property-type").json()
        assert data["run_id"] == active_path_activation.run_id

    def test_data_is_list(self, client, active_path_activation):
        data = client.get("/eda/district-property-type").json()
        assert isinstance(data["data"], list)

    def test_item_has_required_fields(self, client, active_path_activation):
        data = client.get("/eda/district-property-type").json()
        for item in data["data"]:
            assert "district" in item
            assert "property_type" in item
            assert "median_price" in item
            assert "sample_count" in item

    def test_district_labels_are_strings(self, client, active_path_activation):
        """district_code phải được map sang tên tiếng Việt."""
        data = client.get("/eda/district-property-type").json()
        for item in data["data"]:
            assert isinstance(item["district"], str)
            assert item["district"] != ""

    def test_quận_7_maps_correctly(self, client, active_path_activation):
        """district_code=18 → 'quận 7'."""
        data = client.get("/eda/district-property-type").json()
        quan7_items = [d for d in data["data"] if d["district"] == "quận 7"]
        assert len(quan7_items) > 0

    def test_property_type_labels_are_strings(self, client, active_path_activation):
        data = client.get("/eda/district-property-type").json()
        for item in data["data"]:
            assert isinstance(item["property_type"], str)


class TestScatterVersion:
    def test_404_when_no_active_model(self, client):
        assert client.get("/eda/scatter/version").status_code == 404

    def test_returns_run_id(self, client, active_path_activation):
        data = client.get("/eda/scatter/version").json()
        assert data["run_id"] == active_path_activation.run_id

    def test_returns_updated_at(self, client, active_path_activation):
        data = client.get("/eda/scatter/version").json()
        assert "updated_at" in data


class TestScatterFile:
    def test_404_when_no_active_model(self, client):
        assert client.get("/eda/scatter/file").status_code == 404

    def test_returns_csv_content(self, client, active_path_activation):
        """Trả về FileResponse với CSV."""
        response = client.get("/eda/scatter/file")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    def test_csv_has_cache_header(self, client, active_path_activation):
        """Cache-Control header phải có max-age=86400."""
        response = client.get("/eda/scatter/file")
        assert response.status_code == 200
        assert "86400" in response.headers.get("cache-control", "")

    def test_csv_filename_is_scatter(self, client, active_path_activation):
        response = client.get("/eda/scatter/file")
        assert response.status_code == 200
        content_disp = response.headers.get("content-disposition", "")
        assert "scatter.csv" in content_disp

    def test_404_when_scatter_file_missing(self, client, db_session, training_run_success):
        """File scatter bị xóa → 404."""
        from app.db.models import PathActivation
        activation = PathActivation(
            run_id=training_run_success.id,
            path_model="media/model_ai/rf_test.pkl",
            path_scatter="media/scatter/nonexistent_file.csv",
            path_data="data/data.csv",
            is_active=True,
        )
        db_session.add(activation)
        db_session.commit()

        response = client.get("/eda/scatter/file")
        assert response.status_code == 404
