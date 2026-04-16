import json
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.service.goong import get_coordinates_from_goong
from app.service.predict_service import predict as ml_predict

router = APIRouter(prefix="/chat", tags=["chat"])

# ---------------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------------

ADDRESS_ = {
    'bình chánh': 0, 'bình tân': 1, 'bình thạnh': 2, 'cần giờ': 3,
    'củ chi': 4, 'gò vấp': 5, 'hóc môn': 6, 'nhà bè': 7, 'phú nhuận': 8,
    'quận 1': 9, 'quận 10': 10, 'quận 11': 11, 'quận 12': 12,
    'quận 2': 13, 'quận 3': 14, 'quận 4': 15, 'quận 5': 16,
    'quận 6': 17, 'quận 7': 18, 'quận 8': 19, 'quận 9': 20,
    'thủ đức': 21, 'tân bình': 22, 'tân phú': 23,
}

REAL_ESTATE_ = {
    'căn hộ chung cư': 0, 'nhà riêng': 2,
    'nhà biệt thự, liền kề': 3, 'nhà mặt phố': 4, 'bán đất': 7,
}

SESSION_TIMEOUT_MINUTES = 30 #Thời gian một phiên chat với bot

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_sessions: dict[str, "SessionData"] = {}  # Lưu trữ tất cả session


@dataclass
class ChatState:  # Thu thập thông tin nhà đất từ người dùng

    loai_nha_dat: Optional[int] = None
    <!-- loai_nha_dat_text: Optional[text] = None -->
    dia_chi_text: Optional[str] = None
    dia_chi_code: Optional[int] = None
    dien_tich: Optional[float] = None
    so_tang: Optional[int] = None
    phong_ngu: Optional[int] = None
    mat_tien: Optional[float] = None
    toa_do_x: Optional[float] = None
    toa_do_y: Optional[float] = None
    last_geocoded_address: Optional[str] = None
    auto_filled: set = field(default_factory=set)


@dataclass
class SessionData: # Một phiên hoạt động với bot
    state: ChatState  # Lưu trữ thông tin thu thập
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # Thời gian hoạt động gần nhất

    def touch(self):  # Đánh dấu hoạt động, cập nhật thời gian
        self.last_activity = datetime.now(timezone.utc)

    def is_expired(self) -> bool: # Check hết hạn
        delta = datetime.now(timezone.utc) - self.last_activity
        return delta.total_seconds() > SESSION_TIMEOUT_MINUTES * 60


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):  # Request body từ người dùng, gửi session và message
    session_id: Optional[str] = None
    message: str


# ---------------------------------------------------------------------------
# Helpers (ported từ test.py)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# User gõ bằng Unikey kiểu NFD
# user_msg = "căn hộ chung cư"   # c-a-ă-n = NFD (ă tách thành a + dấu)
#
# Code hardcode kiểu NFC
# REAL_ESTATE_["căn hộ chung cư"]  # ă = 1 ký tự NFC
#
# Không normalize → không tìm thấy loại BĐS → chatbot bị lỗi
# user_msg in REAL_ESTATE_  # False ← sai
#
# Sau normalize("NFKC")
# normalize(user_msg) in normalize(REAL_ESTATE_)  # True ← đúng
# ---------------------------------------------------------------------------
def _norm_text(s: str) -> str:   # Chuẩn hóa chữ, đảm bảo các chữ như nhau về mặt code    
    return unicodedata.normalize("NFKC", s.strip().lower())

# ---------------------------------------------------------------------------
# s = "Quận 7, Bình Thạnh"
#
# Bước 1: NFD — tách ký tự có dấu ra thành (ký tự gốc + dấu riêng)
# s = unicodedata.normalize("NFD", s)
# "Quận" → Q-u-a-̣-̂-n  (ậ tách thành: a + dấu mũ + dấu nặng)
#
# Bước 2: Lọc bỏ category "Mn"
# s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
# "Mn" = Mark, Nonspacing = các dấu phụ (huyền, sắc, nặng, hỏi, ngã, mũ, móc...)
# Giữ lại: chữ cái gốc, số, khoảng trắng
# Kết quả: "Quan 7, Binh Thanh"
#
# Bước 3: NFKC — compose lại, chuẩn hóa
# return unicodedata.normalize("NFKC", s)
# → "Quan 7, Binh Thanh"
# ---------------------------------------------------------------------------
def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFKC", s)


_DONE_SIGNALS = {
    "ok", "okay", "oke", "o k", "xong", "xong rồi", "xong r",
    "đủ", "đủ r", "đủ rồi", "đã đủ", "đã đủ rồi", "đủ thông tin",
    "được rồi", "được", "dc rồi", "dc r",
    "tiến hành", "dự đoán đi", "bắt đầu dự đoán", "dự đoán luôn",
    "xác nhận", "chốt", "chốt luôn",
    "du", "du r", "du roi", "da du", "da du roi", "du thong tin",
    "duoc roi", "duoc", "dc roi",
    "tien hanh", "du doan di", "bat dau du doan", "du doan luon",
    "xac nhan", "chot", "chot luon",
}


def _is_done_signal(text: str) -> bool:  # Check coi người dùng muốn đoán chưa
    t = _strip_accents(_norm_text(text))
    return t in _DONE_SIGNALS or _norm_text(text) in _DONE_SIGNALS


def _find_district_code(address_text: str) -> Optional[int]:  # Kiểm tra có loại nhà đất nào trong tin nhắn không
    t = _strip_accents(_norm_text(address_text))
    for k, code in ADDRESS_.items():
        if _strip_accents(_norm_text(k)) in t:
            return code
    return None

# Điền nếu đã có loại nhà đất text mà chưa có loại nhà đất code
def _fill_if_has_property_type_text(): 
    pass

# Tìm code của loại nhà đất
def _parse_real_estate(text: str) -> Optional[int]:  
    t = _strip_accents(_norm_text(text))
    # thử parse số
    m = re.search(r"(\d+)", t)
    if m:
        n = int(m.group(1))
        if n in set(REAL_ESTATE_.values()):
            return n
    for name, code in REAL_ESTATE_.items():
        if _strip_accents(_norm_text(name)) in t:
            return code
    return None


# ---------------------------
# Lọc tin nhắn
# Hàm trả vê dạng dict data đã lọc từ tin nhắn người dùng
# ---------------------------
def _extract_from_text(text: str) -> dict:   
    result: dict = {}
    t = _norm_text(text)
    t_na = _strip_accents(t)

    # Lọc diện tích
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|met vuong|mét vuông)", t_na)
    if m:
        try:
            result["area_m2"] = float(m.group(1).replace(",", "."))
        except ValueError:
            pass

    # Lọc loại nhà đất
    for name in sorted(REAL_ESTATE_, key=len, reverse=True):
        if _strip_accents(_norm_text(name)) in t_na:
            result["real_estate"] = name
            break

    # Lọc quận
    for district in sorted(ADDRESS_, key=len, reverse=True):
        if _strip_accents(_norm_text(district)) in t_na:
            result["district_text"] = district
            break

    # Lọc số tầng
    m = re.search(r"(\d+)\s*(?:tang|lau|tầng|lầu)\b", t_na)
    if m:
        try:
            result["floors"] = int(m.group(1))
        except ValueError:
            pass

    # Lọc phòng ngủ
    m = re.search(r"(\d+)\s*(?:phong ngu|phòng ngủ|\bpn\b)", t_na)
    if m:
        try:
            result["bedrooms"] = int(m.group(1))
        except ValueError:
            pass

    # Lọc mặt tiền
    m = re.search(r"(?:mat tien|mặt tiền|ngang)\s*(\d+(?:[.,]\d+)?)\s*m\b", t_na)
    if m:
        try:
            result["frontage_m"] = float(m.group(1).replace(",", "."))
        except ValueError:
            pass

    return result


# Thông tin nào còn thiếu
def _missing_required(state: ChatState) -> list[str]:
    missing = []
    if state.loai_nha_dat is None:
        missing.append("loại nhà đất")
    if state.dia_chi_text is None:
        missing.append("địa chỉ")
    if state.dia_chi_code is None:
        missing.append("quận/huyện")
    if state.dien_tich is None:
        missing.append("diện tích (m²)")
    if state.toa_do_x is None or state.toa_do_y is None:
        missing.append("tọa độ (geocoding)")
    return missing

# Chạy llm lọc thông tin
def _llm_extract(llm: OpenAI, llm_model: str, user_text: str) -> dict:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system = f.read()
    except FileNotFoundError:
        system = "Trích xuất thông tin bất động sản từ câu người dùng."

    schema = {
        "name": "real_estate_extract",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "user_done": {"type": "boolean"},
                "extracted": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "real_estate":   {"type": ["string", "null"]},
                        "address_text":  {"type": ["string", "null"]},
                        "district_text": {"type": ["string", "null"]},
                        "area_m2":       {"type": ["number", "null"]},
                        "floors":        {"type": ["integer", "null"]},
                        "bedrooms":      {"type": ["integer", "null"]},
                        "frontage_m":    {"type": ["number", "null"]},
                    },
                    "required": ["real_estate", "address_text", "district_text",
                                 "area_m2", "floors", "bedrooms", "frontage_m"],
                },
            },
            "required": ["user_done", "extracted"],
        },
    }
    try:
        resp = llm.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Người dùng nói:\n{user_text}"},
            ],
            response_format={"type": "json_schema", "json_schema": schema},
            temperature=0.1,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"user_done": False, "extracted": {k: None for k in
                ["real_estate", "address_text", "district_text",
                 "area_m2", "floors", "bedrooms", "frontage_m"]}}


# llm hỏi thông tin thêm về loại nhà đất mà người dùng đang hướng tới
def _llm_converse(llm: OpenAI, llm_model: str, state: ChatState) -> str:
    loai = state.loai_nha_dat
    loai_name = next((n for n, c in REAL_ESTATE_.items() if c == loai), None)

    if loai == 0:
        optional_fields = {"số phòng ngủ": state.phong_ngu}
    elif loai == 7:
        optional_fields = {"mặt tiền": state.mat_tien}
    else:
        optional_fields = {
            "số phòng ngủ": state.phong_ngu,
            "mặt tiền": state.mat_tien,
            "số tầng": state.so_tang,
        }

    miss_optional = [k for k, v in optional_fields.items() if v is None]
    miss_required = _missing_required(state)

    lines = []
    if loai_name:
        lines.append(f"- Loại nhà đất: {loai_name} ✓")
    else:
        lines.append("- Loại nhà đất: chưa có")
    lines.append(f"- Địa chỉ: {state.dia_chi_text or 'chưa có'}" + (" ✓" if state.dia_chi_text else ""))
    lines.append(f"- Diện tích: {state.dien_tich} m² ✓" if state.dien_tich else "- Diện tích: chưa có")
    if loai not in {7} and state.phong_ngu is not None:
        lines.append(f"- Phòng ngủ: {int(state.phong_ngu)} ✓")
    if loai not in {0, 7} and state.so_tang is not None:
        lines.append(f"- Số tầng: {int(state.so_tang)} ✓")
    if loai not in {0} and state.mat_tien is not None:
        lines.append(f"- Mặt tiền: {state.mat_tien} m ✓")
    state_summary = "\n".join(lines)

    if miss_required:
        situation = f"Còn thiếu bắt buộc: {', '.join(miss_required)}."
        instruction = "Hỏi 1 câu ngắn để lấy trường còn thiếu nhất."
    elif miss_optional:
        situation = f"Đủ thông tin bắt buộc. Chưa có: {', '.join(miss_optional)}."
        instruction = (
            "Xác nhận thông tin đã có (ngắn gọn 2-3 dòng), "
            f"rồi hỏi về {', '.join(miss_optional)}. "
            "Kết thúc bằng: 'Hoặc gõ ok để dự đoán ngay!'"
        )
    else:
        situation = "Đã có đủ tất cả thông tin."
        instruction = "Xác nhận ngắn gọn và nói 'Gõ ok để tiến hành dự đoán nhé!'"

    prompt = (
        "Bạn là chatbot hỗ trợ dự đoán giá BĐS TP.HCM. Trả lời tiếng Việt, thân thiện, ngắn gọn.\n\n"
        f"Thông tin đang có:\n{state_summary}\n\n"
        f"Tình huống: {situation}\n"
        f"Yêu cầu: {instruction}\n\n"
        "Trả về CHỈ câu trả lời cho người dùng, không thêm gì khác."
    )
    try:
        resp = llm.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=250,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        if miss_required:
            return f"Mình cần thêm: {', '.join(miss_required)}. Bạn cung cấp giúp mình nhé!"
        return "Mình đã có đủ thông tin. Gõ ok để tiến hành dự đoán nhé!"


# Giải thích về giá và các loại thông tin đã có
def _explain_prediction(llm: OpenAI, llm_model: str, state: ChatState,
                        price_per_m2: float, total_price: float) -> str:
    from app.service.predict_service import haversine
    loai_name = next((n for n, c in REAL_ESTATE_.items() if c == state.loai_nha_dat), "không rõ")
    district_name = next((k for k, v in ADDRESS_.items() if v == state.dia_chi_code), "không rõ")
    distance_km = haversine(state.toa_do_x, state.toa_do_y) if state.toa_do_x else None
    price_ty = total_price / 1_000

    loai = state.loai_nha_dat
    details = []
    if state.so_tang and loai not in {0, 7}:
        details.append(f"{int(state.so_tang)} tầng")
    if state.phong_ngu and loai not in {7}:
        details.append(f"{int(state.phong_ngu)} phòng ngủ")
    if state.mat_tien and loai not in {0}:
        details.append(f"mặt tiền {state.mat_tien}m")

    prompt = (
        f"Bạn là chuyên gia bất động sản TP.HCM. Hãy giải thích ngắn gọn (3 gạch đầu dòng) "
        f"tại sao BĐS sau được định giá ở mức này:\n\n"
        f"- Loại: {loai_name}\n"
        f"- Khu vực: {district_name}\n"
        f"- Diện tích: {state.dien_tich} m²\n"
        + (f"- Thông tin thêm: {', '.join(details)}\n" if details else "")
        + (f"- Cách trung tâm: {distance_km:.1f} km\n" if distance_km else "")
        + f"- Giá dự đoán: {price_per_m2:,.1f} triệu/m² (~{price_ty:,.2f} tỷ VND)\n\n"
        f"Mỗi điểm 1-2 câu, tiếng Việt tự nhiên."
    )
    try:
        resp = llm.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


# hợp nhất thông tin đã extract được với state để cập nhật dữ liệu muốn dự đoán
def _update_state_from_merged(state: ChatState, merged: dict, median_series=None):
    if merged.get("real_estate"):
        loai = _parse_real_estate(str(merged["real_estate"]))
        if loai is not None:
            state.loai_nha_dat = loai
            if median_series is not None:
                if loai == 0:
                    state.so_tang = float(median_series.get("số tầng", 0))
                    state.mat_tien = float(median_series.get("mặt tiền", 0))
                    state.auto_filled.update({"so_tang", "mat_tien"})
                elif loai == 7:
                    state.so_tang = float(median_series.get("số tầng", 0))
                    state.phong_ngu = float(median_series.get("phòng ngủ", 0))
                    state.auto_filled.update({"so_tang", "phong_ngu"})

    if merged.get("address_text"):
        state.dia_chi_text = str(merged["address_text"]).strip()

    district_text = merged.get("district_text")
    if district_text:
        dc = _find_district_code(str(district_text))
        if dc is not None:
            state.dia_chi_code = dc
        if not state.dia_chi_text:
            state.dia_chi_text = str(district_text).strip()

    if state.dia_chi_text:
        t = _strip_accents(_norm_text(state.dia_chi_text))
        if not any(kw in t for kw in ("hcm", "ho chi minh", "tp", "tphcm")):
            state.dia_chi_text = state.dia_chi_text + ", TP.HCM"

    if state.dia_chi_code is None and state.dia_chi_text:
        state.dia_chi_code = _find_district_code(state.dia_chi_text)

    if merged.get("area_m2") is not None:
        try:
            v = float(merged["area_m2"])
            if v > 0:
                state.dien_tich = v
        except Exception:
            pass

    if merged.get("floors") is not None:
        try:
            v = int(merged["floors"])
            if v > 0:
                state.so_tang = v
        except Exception:
            pass

    if merged.get("bedrooms") is not None:
        try:
            v = int(merged["bedrooms"])
            if v > 0:
                state.phong_ngu = v
        except Exception:
            pass

    if merged.get("frontage_m") is not None:
        try:
            v = float(merged["frontage_m"])
            if v > 0:
                state.mat_tien = v
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Endpoint
- Xóa các session hết hạn. 
- Trích xuất tin nhắn từ người dùng qua llm và extract
- lọc xong thì merge lại
- Lấy thông tin tọa độ
# ---------------------------------------------------------------------------

@router.post("")
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    # Dọn session hết hạn
    expired = [sid for sid, sd in _sessions.items() if sd.is_expired()]
    for sid in expired:
        del _sessions[sid]

    # Lấy hoặc tạo session
    session_id = body.session_id
    if not session_id or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = SessionData(state=ChatState())

    session = _sessions[session_id]
    session.touch()
    state = session.state

    message = body.message.strip()
    cmd = _norm_text(message)

    # Lệnh đặc biệt
    if cmd in {"exit", "quit", "bye", "thoat", "thoát"}:
        del _sessions[session_id]
        return {"session_id": session_id, "reply": "Tạm biệt!",
                "is_prediction": False, "prediction": None, "state_complete": False}

    if cmd == "reset":
        _sessions[session_id] = SessionData(state=ChatState())
        return {"session_id": session_id, "reply": "Mình đã xoá thông tin. Bắt đầu lại nhé.",
                "is_prediction": False, "prediction": None, "state_complete": False}

    # Khởi tạo LLM
    openai_key = os.getenv("OPENAI_KEY")
    llm_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = OpenAI(api_key=openai_key) if openai_key else None

    force_done = _is_done_signal(message)
    llm_out = None

    if not force_done and llm:
        llm_out = _llm_extract(llm, llm_model, message)
        extracted = (llm_out or {}).get("extracted") or {}
        py = _extract_from_text(message)
        merged = {**py}
        for k, v in extracted.items():
            if v is not None:
                merged[k] = v
        _update_state_from_merged(state, merged)
    elif not force_done:
        py = _extract_from_text(message)
        _update_state_from_merged(state, py)

    # Geocode
    if state.dia_chi_text and (state.toa_do_x is None or state.toa_do_y is None):
        geo = get_coordinates_from_goong(state.dia_chi_text)
        if geo:
            state.last_geocoded_address = geo.get("address")
            state.toa_do_x = geo.get("x")
            state.toa_do_y = geo.get("y")

    user_done = force_done or bool((llm_out or {}).get("user_done", False))

    if user_done:
        missing = _missing_required(state)
        if missing:
            hint = ""
            if state.dia_chi_text and state.dia_chi_code is None:
                hint = " Bạn cho mình biết quận/huyện (vd: Quận 7 / Thủ Đức) nhé."
            reply = "Mình kiểm tra lại thì vẫn còn thiếu: " + ", ".join(missing) + "." + hint
            return {"session_id": session_id, "reply": reply,
                    "is_prediction": False, "prediction": None, "state_complete": False}

        payload = {
            "loại nhà đất": state.loai_nha_dat,
            "địa chỉ": state.dia_chi_code,
            "diện tích": state.dien_tich,
            "mặt tiền": state.mat_tien,
            "phòng ngủ": state.phong_ngu,
            "tọa độ x": state.toa_do_x,
            "tọa độ y": state.toa_do_y,
            "số tầng": state.so_tang,
        }

        price_per_m2, total_price = ml_predict(payload, db_session=db)
        if price_per_m2 is None:
            return {"session_id": session_id,
                    "reply": "Dự đoán thất bại. Hệ thống chưa có model — hãy chạy retrain trước.",
                    "is_prediction": False, "prediction": None, "state_complete": True}

        explanation = ""
        if llm:
            explanation = _explain_prediction(llm, llm_model, state, price_per_m2, total_price)

        reply = (
            f"Kết quả dự đoán:\n"
            f"- Giá/m²: {price_per_m2:,.1f} triệu VND/m²\n"
            f"- Tổng giá (ước tính): {total_price / 1_000:,.2f} tỷ VND"
        )
        if explanation:
            reply += f"\n\nLý do giá ở mức này:\n{explanation}"
        reply += (
            "\n\nBạn muốn làm gì tiếp theo?\n"
            "• Sửa thông tin: nói trực tiếp (vd: 'đổi diện tích 100m2')\n"
            "• Dự đoán lại: gõ 'ok'\n"
            "• Bắt đầu mới: gõ 'reset'"
        )

        return {
            "session_id": session_id,
            "reply": reply,
            "is_prediction": True,
            "prediction": {"price_per_m2": price_per_m2, "total_price": total_price},
            "state_complete": True,
        }

    # Sinh câu hỏi tiếp theo
    if llm:
        assistant_message = _llm_converse(llm, llm_model, state)
    else:
        missing = _missing_required(state)
        assistant_message = (
            f"Mình cần thêm: {', '.join(missing)}." if missing
            else "Mình đã có đủ thông tin. Gõ ok để tiến hành dự đoán nhé!"
        )

    return {
        "session_id": session_id,
        "reply": assistant_message,
        "is_prediction": False,
        "prediction": None,
        "state_complete": False,
    }
