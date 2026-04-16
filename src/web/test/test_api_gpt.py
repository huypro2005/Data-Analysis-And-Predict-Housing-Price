"""
Integration tests cho POST /chat (chatbot)
"""
import pytest
from unittest.mock import MagicMock, patch

from app.api.api_gpt import _sessions, _extract_from_text, _is_done_signal, _find_district_code


# ---------------------------------------------------------------------------
# Helper — mock toàn bộ external calls
# ---------------------------------------------------------------------------

def _make_llm_extract_result(extracted: dict = None, user_done: bool = False):
    """Tạo kết quả giả từ LLM extract."""
    default = {
        "real_estate": None, "address_text": None, "district_text": None,
        "area_m2": None, "floors": None, "bedrooms": None, "frontage_m": None,
    }
    if extracted:
        default.update(extracted)
    return {"user_done": user_done, "extracted": default}


@pytest.fixture(autouse=True)
def clear_sessions():
    """Dọn sạch _sessions trước/sau mỗi test."""
    _sessions.clear()
    yield
    _sessions.clear()


# ---------------------------------------------------------------------------
# Unit tests — helpers
# ---------------------------------------------------------------------------

class TestIsDoneSignal:
    @pytest.mark.parametrize("text", [
        "ok", "OK", "okay", "xong", "đủ rồi", "tiến hành",
        "xác nhận", "chốt", "du roi", "tien hanh",
    ])
    def test_recognizes_done_signals(self, text):
        assert _is_done_signal(text) is True

    @pytest.mark.parametrize("text", [
        "nhà riêng", "80m2", "quận 7", "bắt đầu",
    ])
    def test_rejects_non_done_signals(self, text):
        assert _is_done_signal(text) is False


class TestExtractFromText:
    def test_extracts_area(self):
        result = _extract_from_text("căn hộ 80m2 ở quận 7")
        assert result.get("area_m2") == pytest.approx(80.0)

    def test_extracts_area_m2_unicode(self):
        result = _extract_from_text("diện tích 120 m²")
        assert result.get("area_m2") == pytest.approx(120.0)

    def test_extracts_district(self):
        result = _extract_from_text("nhà riêng ở quận 7, 80m2")
        assert result.get("district_text") == "quận 7"

    def test_extracts_real_estate(self):
        result = _extract_from_text("căn hộ chung cư 70m2")
        assert result.get("real_estate") == "căn hộ chung cư"

    def test_extracts_floors(self):
        result = _extract_from_text("nhà 3 tầng")
        assert result.get("floors") == 3

    def test_extracts_bedrooms(self):
        result = _extract_from_text("2 phòng ngủ")
        assert result.get("bedrooms") == 2

    def test_extracts_frontage(self):
        result = _extract_from_text("mặt tiền 5m")
        assert result.get("frontage_m") == pytest.approx(5.0)

    def test_no_extraction_from_empty_text(self):
        result = _extract_from_text("xin chào")
        assert not any(v is not None for v in result.values())


class TestFindDistrictCode:
    def test_quan_7_returns_18(self):
        assert _find_district_code("quận 7") == 18

    def test_thu_duc_returns_21(self):
        assert _find_district_code("thủ đức") == 21

    def test_binh_tan_returns_1(self):
        assert _find_district_code("bình tân") == 1

    def test_returns_none_for_unknown(self):
        assert _find_district_code("đà nẵng") is None

    def test_case_insensitive(self):
        assert _find_district_code("QUẬN 7") == 18


# ---------------------------------------------------------------------------
# Integration tests — POST /chat
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def test_creates_new_session_when_none(self, client):
        """session_id=null → tạo session mới."""
        with patch("app.api.api_gpt._llm_extract", return_value=_make_llm_extract_result()), \
             patch("app.api.api_gpt._llm_converse", return_value="Bạn muốn mua loại BĐS gì?"):
            response = client.post("/chat", json={"session_id": None, "message": "xin chào"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] is not None
        assert len(data["session_id"]) > 0

    def test_reuses_existing_session(self, client):
        """Gửi cùng session_id → cùng session, state được giữ."""
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({"real_estate": "nhà riêng"})), \
             patch("app.api.api_gpt._llm_converse", return_value="Diện tích bao nhiêu?"), \
             patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            r1 = client.post("/chat", json={"session_id": None, "message": "nhà riêng"})
        sid = r1.json()["session_id"]
        assert sid in _sessions

        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({"area_m2": 80})), \
             patch("app.api.api_gpt._llm_converse", return_value="Còn thiếu địa chỉ"), \
             patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            r2 = client.post("/chat", json={"session_id": sid, "message": "80m2"})
        assert r2.json()["session_id"] == sid
        # State được giữ: loai_nha_dat đã được set từ lần 1
        assert _sessions[sid].state.loai_nha_dat == 2   # nhà riêng = code 2

    def test_reset_command_clears_state(self, client):
        """Lệnh 'reset' → session mới, state sạch."""
        # Tạo session với state có dữ liệu
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({"real_estate": "nhà riêng"})), \
             patch("app.api.api_gpt._llm_converse", return_value="Ok"), \
             patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            r1 = client.post("/chat", json={"session_id": None, "message": "nhà riêng"})
        sid = r1.json()["session_id"]

        response = client.post("/chat", json={"session_id": sid, "message": "reset"})
        assert response.status_code == 200
        # Session bị reset → state sạch
        assert _sessions[sid].state.loai_nha_dat is None

    def test_exit_command_removes_session(self, client):
        """Lệnh 'exit' → session bị xóa."""
        with patch("app.api.api_gpt._llm_extract", return_value=_make_llm_extract_result()), \
             patch("app.api.api_gpt._llm_converse", return_value="Xin chào"):
            r1 = client.post("/chat", json={"session_id": None, "message": "hello"})
        sid = r1.json()["session_id"]

        r2 = client.post("/chat", json={"session_id": sid, "message": "exit"})
        assert r2.status_code == 200
        assert sid not in _sessions

    def test_unknown_session_creates_new(self, client):
        """session_id không tồn tại → tạo session mới (không báo lỗi)."""
        with patch("app.api.api_gpt._llm_extract", return_value=_make_llm_extract_result()), \
             patch("app.api.api_gpt._llm_converse", return_value="Xin chào"):
            response = client.post("/chat", json={
                "session_id": "nonexistent-uuid-abc123", "message": "hello"
            })
        assert response.status_code == 200

    # ------------------------------------------------------------------
    # Response structure
    # ------------------------------------------------------------------

    def test_response_has_required_fields(self, client):
        with patch("app.api.api_gpt._llm_extract", return_value=_make_llm_extract_result()), \
             patch("app.api.api_gpt._llm_converse", return_value="Xin chào"):
            data = client.post("/chat", json={"session_id": None, "message": "hi"}).json()
        for field in ["session_id", "reply", "is_prediction", "prediction", "state_complete"]:
            assert field in data

    def test_non_prediction_reply_has_null_prediction(self, client):
        with patch("app.api.api_gpt._llm_extract", return_value=_make_llm_extract_result()), \
             patch("app.api.api_gpt._llm_converse", return_value="Bạn muốn mua gì?"):
            data = client.post("/chat", json={"session_id": None, "message": "hello"}).json()
        assert data["is_prediction"] is False
        assert data["prediction"] is None

    # ------------------------------------------------------------------
    # State extraction from message
    # ------------------------------------------------------------------

    def test_extracts_area_from_message(self, client):
        """80m2 trong tin nhắn phải được trích xuất vào state."""
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({"area_m2": 80})), \
             patch("app.api.api_gpt._llm_converse", return_value="Diện tích 80m2 đã nhận"), \
             patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            r = client.post("/chat", json={"session_id": None, "message": "80m2"})
        sid = r.json()["session_id"]
        assert _sessions[sid].state.dien_tich == pytest.approx(80.0)

    def test_extracts_district_from_message(self, client):
        """'quận 7' phải được map sang district_code=18."""
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({"district_text": "quận 7"})), \
             patch("app.api.api_gpt._llm_converse", return_value="Quận 7 đã nhận"), \
             patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            r = client.post("/chat", json={"session_id": None, "message": "quận 7"})
        sid = r.json()["session_id"]
        assert _sessions[sid].state.dia_chi_code == 18

    def test_geocoding_called_when_address_available(self, client):
        """Khi có địa chỉ → Goong API được gọi."""
        mock_geo = {"address": "Quận 7, TP.HCM", "x": 10.732, "y": 106.721}
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result(
                       {"district_text": "quận 7", "address_text": "quận 7"})), \
             patch("app.api.api_gpt._llm_converse", return_value="Đã nhận địa chỉ"), \
             patch("app.api.api_gpt.get_coordinates_from_goong", return_value=mock_geo) as mock_goong:
            r = client.post("/chat", json={"session_id": None, "message": "quận 7"})
        mock_goong.assert_called_once()
        sid = r.json()["session_id"]
        assert _sessions[sid].state.toa_do_x == pytest.approx(10.732)

    # ------------------------------------------------------------------
    # Done signal → prediction
    # ------------------------------------------------------------------

    def test_done_signal_triggers_missing_check(self, client):
        """'ok' khi chưa đủ thông tin → reply có thông báo thiếu."""
        with patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            r = client.post("/chat", json={"session_id": None, "message": "ok"})
        data = r.json()
        assert data["is_prediction"] is False
        assert "thiếu" in data["reply"].lower()

    def test_done_with_complete_info_calls_predict(self, client, active_path_activation):
        """Khi đủ thông tin + 'ok' → gọi predict và trả về kết quả."""
        from test.helpers import make_mock_pipeline
        mock_pl = make_mock_pipeline(predict_log_value=3.8)

        # Tạo session với đầy đủ thông tin
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({
                       "real_estate": "nhà riêng", "district_text": "quận 7",
                       "address_text": "quận 7", "area_m2": 80,
                   })), \
             patch("app.api.api_gpt._llm_converse", return_value="Gõ ok để dự đoán"), \
             patch("app.api.api_gpt.get_coordinates_from_goong",
                   return_value={"address": "Quận 7", "x": 10.732, "y": 106.721}):
            r1 = client.post("/chat", json={"session_id": None, "message": "nhà riêng 80m2 quận 7"})
        sid = r1.json()["session_id"]

        # Gửi ok với state đầy đủ, mock predict
        with patch("app.api.api_gpt.ml_predict", return_value=(55.0, 4400.0)) as mock_pred, \
             patch("app.api.api_gpt.get_coordinates_from_goong",
                   return_value={"address": "Quận 7", "x": 10.732, "y": 106.721}), \
             patch("app.api.api_gpt._explain_prediction", return_value="Giá hợp lý do..."):
            r2 = client.post("/chat", json={"session_id": sid, "message": "ok"})
        data = r2.json()

        mock_pred.assert_called_once()
        assert data["is_prediction"] is True
        assert data["prediction"]["price_per_m2"] == pytest.approx(55.0)
        assert data["prediction"]["total_price"] == pytest.approx(4400.0)

    def test_prediction_reply_contains_price_info(self, client, active_path_activation):
        """Reply khi dự đoán phải chứa thông tin giá."""
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({
                       "real_estate": "nhà riêng", "district_text": "quận 7",
                       "address_text": "quận 7", "area_m2": 80,
                   })), \
             patch("app.api.api_gpt._llm_converse", return_value="Gõ ok"), \
             patch("app.api.api_gpt.get_coordinates_from_goong",
                   return_value={"address": "Quận 7", "x": 10.732, "y": 106.721}):
            r1 = client.post("/chat", json={"session_id": None, "message": "nhà riêng 80m2 quận 7"})
        sid = r1.json()["session_id"]

        with patch("app.api.api_gpt.ml_predict", return_value=(55.0, 4400.0)), \
             patch("app.api.api_gpt.get_coordinates_from_goong",
                   return_value={"address": "Quận 7", "x": 10.732, "y": 106.721}), \
             patch("app.api.api_gpt._explain_prediction", return_value=""):
            r2 = client.post("/chat", json={"session_id": sid, "message": "ok"})

        reply = r2.json()["reply"]
        assert "55" in reply or "triệu" in reply.lower()

    def test_predict_failure_returns_error_message(self, client, db_session):
        """predict trả về (None, None) → reply thông báo lỗi."""
        with patch("app.api.api_gpt._llm_extract",
                   return_value=_make_llm_extract_result({
                       "real_estate": "nhà riêng", "district_text": "quận 7",
                       "address_text": "quận 7", "area_m2": 80,
                   })), \
             patch("app.api.api_gpt._llm_converse", return_value="Gõ ok"), \
             patch("app.api.api_gpt.get_coordinates_from_goong",
                   return_value={"address": "Quận 7", "x": 10.732, "y": 106.721}):
            r1 = client.post("/chat", json={"session_id": None, "message": "nhà riêng 80m2 quận 7"})
        sid = r1.json()["session_id"]

        with patch("app.api.api_gpt.ml_predict", return_value=(None, None)), \
             patch("app.api.api_gpt.get_coordinates_from_goong",
                   return_value={"address": "Quận 7", "x": 10.732, "y": 106.721}):
            r2 = client.post("/chat", json={"session_id": sid, "message": "ok"})
        data = r2.json()
        assert data["is_prediction"] is False

    # ------------------------------------------------------------------
    # LLM fallback (no OPENAI_KEY)
    # ------------------------------------------------------------------

    def test_works_without_openai_key(self, client, monkeypatch):
        """Không có OPENAI_KEY → dùng regex extraction, không crash."""
        monkeypatch.delenv("OPENAI_KEY", raising=False)
        with patch("app.api.api_gpt.get_coordinates_from_goong", return_value=None):
            response = client.post("/chat", json={"session_id": None, "message": "nhà riêng 80m2 quận 7"})
        assert response.status_code == 200
        data = response.json()
        assert data["reply"] is not None
