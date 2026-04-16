# API Documentation — Hệ thống Dự đoán Giá BĐS TP.HCM

**Base URL:** `http://localhost:8000`  
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)  
**Format:** JSON (Content-Type: application/json)

---

## Mục lục

1. [Predict — Dự đoán giá](#1-predict--dự-đoán-giá)
2. [Retrain — Quản lý model](#2-retrain--quản-lý-model)
3. [EDA — Phân tích dữ liệu](#3-eda--phân-tích-dữ-liệu)
4. [Feature Importance](#4-feature-importance)
5. [Chat — Chatbot AI](#5-chat--chatbot-ai)
6. [Enums & Mapping](#6-enums--mapping)
7. [Error Codes](#7-error-codes)
8. [Gợi ý luồng Frontend](#8-gợi-ý-luồng-frontend)

---

## 1. Predict — Dự đoán giá

### `POST /predict`

Dự đoán giá BĐS dựa trên thông tin nhà đất.

**Lưu ý:** Phải chạy retrain ít nhất 1 lần trước khi dùng endpoint này.

**Request Body:**

```json
{
  "loại nhà đất": 2,
  "địa chỉ": 18,
  "diện tích": 80.0,
  "mặt tiền": 5.0,
  "phòng ngủ": 2,
  "tọa độ x": 10.73,
  "tọa độ y": 106.72,
  "số tầng": 3
}
```

| Field | Type | Bắt buộc | Mô tả |
|-------|------|----------|-------|
| `loại nhà đất` | int | ✅ | Mã loại BĐS (xem [Enum BĐS](#loại-bất-động-sản)) |
| `địa chỉ` | int | ✅ | Mã quận/huyện (xem [Enum Quận](#quậnhuyện)) |
| `diện tích` | float | ✅ | Diện tích m² (15–500) |
| `tọa độ x` | float | ✅ | Latitude (vĩ độ) |
| `tọa độ y` | float | ✅ | Longitude (kinh độ) |
| `mặt tiền` | float\|null | ❌ | Chiều rộng mặt tiền (m) |
| `phòng ngủ` | int\|null | ❌ | Số phòng ngủ |
| `số tầng` | int\|null | ❌ | Số tầng |

**Response `200`:**

```json
{
  "predicted_price_per_m2": 85.3,
  "predicted_total_price": 6824.0
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `predicted_price_per_m2` | float\|null | Giá/m² (triệu VND). `null` nếu chưa có model |
| `predicted_total_price` | float\|null | Tổng giá ước tính (triệu VND) |

**Ví dụ:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "loại nhà đất": 2,
    "địa chỉ": 18,
    "diện tích": 80.0,
    "mặt tiền": null,
    "phòng ngủ": 2,
    "tọa độ x": 10.73,
    "tọa độ y": 106.72,
    "số tầng": null
  }'
```

---

## 2. Retrain — Quản lý model

### `POST /retrain/trigger`

Kích hoạt retrain model trong background (không block request).

**Điều kiện skip:** Nếu data mới < 100 dòng so với lần train trước, hệ thống tự bỏ qua.

**Request:** Không có body.

**Response `200`:**
```json
{ "message": "Retrain đã được kích hoạt" }
```

**Response `409` — Đang có retrain chạy:**
```json
{ "detail": "Retrain đang chạy (run_id=3)" }
```

> **Frontend tip:** Disable nút "Retrain" khi `GET /retrain/status` trả về `status = "running"`.

---

### `GET /retrain/status`

Trạng thái retrain hiện tại và run gần nhất.

**Response `200`:**
```json
{
  "status": "idle",
  "last_run": {
    "id": 3,
    "triggered_at": "2026-04-09T18:30:00Z",
    "status": "success",
    "new_rows": 450,
    "model_replaced": true
  }
}
```

| Field | Values | Mô tả |
|-------|--------|-------|
| `status` | `"idle"` \| `"running"` | Trạng thái hiện tại |
| `last_run` | object\|null | Run gần nhất, `null` nếu chưa có |
| `last_run.status` | `"running"` \| `"success"` \| `"failed"` \| `"skipped"` | Kết quả run |
| `last_run.model_replaced` | bool\|null | Model có được thay thế không |

---

### `GET /retrain/history`

Lịch sử retrain, phân trang, kèm metrics.

**Query Params:**

| Param | Type | Default | Mô tả |
|-------|------|---------|-------|
| `page` | int | 1 | Số trang |
| `size` | int | 10 | Số item/trang |

**Response `200`:**
```json
{
  "total": 5,
  "page": 1,
  "size": 10,
  "items": [
    {
      "id": 3,
      "triggered_at": "2026-04-09T18:30:00Z",
      "status": "success",
      "new_rows": 450,
      "total_rows": 24880,
      "duration_sec": 187.4,
      "model_replaced": true,
      "metrics": {
        "rmse": 0.243,
        "mae": 0.181,
        "r2": 0.891,
        "prev_rmse": 0.268,
        "prev_mae": 0.196,
        "prev_r2": 0.872
      }
    }
  ]
}
```

| Field | Mô tả |
|-------|-------|
| `metrics.rmse` | Root Mean Squared Error (log scale) — càng thấp càng tốt |
| `metrics.mae` | Mean Absolute Error (log scale) |
| `metrics.r2` | R² score — càng gần 1 càng tốt |
| `metrics.prev_*` | Metrics của model cũ để so sánh |

---

### `GET /retrain/metrics/trend`

Xu hướng RMSE/MAE/R² qua các lần retrain thành công, dùng để vẽ line chart.

**Response `200`:**
```json
{
  "runs": [
    { "run_id": 1, "date": "2026-03-01T10:00:00Z", "rmse": 0.268, "mae": 0.196, "r2": 0.872 },
    { "run_id": 2, "date": "2026-03-15T10:00:00Z", "rmse": 0.251, "mae": 0.188, "r2": 0.883 },
    { "run_id": 3, "date": "2026-04-09T18:30:00Z", "rmse": 0.243, "mae": 0.181, "r2": 0.891 }
  ]
}
```

> **Frontend tip:** Dùng `runs` để vẽ line chart 3 đường: RMSE, MAE, R² theo `date`.

---

## 3. EDA — Phân tích dữ liệu

Tất cả EDA endpoint đều trả về `404` nếu chưa có model active (chưa retrain lần nào).

---

### `GET /eda/price-distribution`

Phân phối giá/m² theo 7 khoảng bin, dùng để vẽ histogram/bar chart.

**Response `200`:**
```json
{
  "run_id": 3,
  "bins": [
    { "label": "0-30",    "min": 0,   "max": 30,   "count": 520  },
    { "label": "30-50",   "min": 30,  "max": 50,   "count": 3840 },
    { "label": "50-70",   "min": 50,  "max": 70,   "count": 5210 },
    { "label": "70-90",   "min": 70,  "max": 90,   "count": 4120 },
    { "label": "90-110",  "min": 90,  "max": 110,  "count": 2300 },
    { "label": "110-130", "min": 110, "max": 130,  "count": 980  },
    { "label": "130+",    "min": 130, "max": 9999, "count": 410  }
  ]
}
```

---

### `GET /eda/district-property-type`

Giá trung vị (triệu/m²) theo từng cặp quận × loại BĐS.

**Response `200`:**
```json
{
  "run_id": 3,
  "data": [
    {
      "district": "quận 7",
      "property_type": "nhà riêng",
      "median_price": 85.2,
      "sample_count": 312
    },
    {
      "district": "quận 1",
      "property_type": "nhà mặt phố",
      "median_price": 320.5,
      "sample_count": 48
    }
  ]
}
```

> **Frontend tip:** Dùng để vẽ heatmap hoặc grouped bar chart (quận × loại BĐS).  
> Nhóm < 10 mẫu đã bị lọc ở backend, không cần filter thêm.

---

### `GET /eda/scatter/version`

Kiểm tra phiên bản scatter data (dùng cho cache control).

**Response `200`:**
```json
{
  "run_id": 3,
  "updated_at": "2026-04-09T18:30:00Z"
}
```

> **Frontend tip:** Cache `run_id` ở localStorage. Nếu `run_id` thay đổi → gọi `/eda/scatter/file` để tải file mới.

---

### `GET /eda/scatter/file`

Tải file CSV scatter plot (tọa độ + giá/m²), tối đa 2000 điểm.

**Response `200`:**  
File CSV với header:

```
tọa độ x,tọa độ y,diện tích,giá/m2
10.73,106.72,80.0,55.3
10.81,106.65,120.0,42.1
...
```

**Headers:**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="scatter.csv"
Cache-Control: max-age=86400
```

> **Frontend tip:** Parse CSV rồi vẽ scatter plot địa lý (lat/lon) với màu sắc theo `giá/m2`.

---

## 4. Feature Importance

### `GET /feature-importance`

Mức độ quan trọng của từng feature trong model, sắp xếp giảm dần.

**Response `200`:**
```json
{
  "run_id": 3,
  "features": [
    { "name": "cách trung tâm", "importance": 0.312 },
    { "name": "diện tích",      "importance": 0.248 },
    { "name": "địa chỉ",       "importance": 0.157 },
    { "name": "loại nhà đất",  "importance": 0.098 },
    { "name": "mặt tiền",      "importance": 0.075 },
    { "name": "phòng ngủ",     "importance": 0.054 },
    { "name": "tọa độ x",      "importance": 0.031 },
    { "name": "tọa độ y",      "importance": 0.018 },
    { "name": "số tầng",       "importance": 0.007 }
  ]
}
```

> **Frontend tip:** Dùng horizontal bar chart, `importance` là giá trị 0–1, tổng ≈ 1.

---

## 5. Chat — Chatbot AI

### `POST /chat`

Chatbot hỏi thông tin BĐS và dự đoán giá qua hội thoại tiếng Việt tự nhiên.

**Cơ chế session:** Session được lưu in-memory trên server, timeout sau **30 phút** không hoạt động. Frontend lưu `session_id` và gửi theo mỗi request.

**Request Body:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "nhà riêng 80m2 quận 7"
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `session_id` | string\|null | UUID phiên. `null` để tạo phiên mới |
| `message` | string | Tin nhắn người dùng (tiếng Việt) |

**Response `200`:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply": "Bạn muốn ước tính giá nhà riêng 80m² tại Quận 7. Bạn có thể cho mình biết thêm số phòng ngủ không? Hoặc gõ ok để dự đoán ngay!",
  "is_prediction": false,
  "prediction": null,
  "state_complete": false
}
```

**Response khi dự đoán thành công (`is_prediction: true`):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "reply": "Kết quả dự đoán:\n- Giá/m²: 85.3 triệu VND/m²\n- Tổng giá (ước tính): 6.82 tỷ VND\n\nLý do giá ở mức này:\n• Quận 7 cách trung tâm ~7km, khu vực đang phát triển...",
  "is_prediction": true,
  "prediction": {
    "price_per_m2": 85.3,
    "total_price": 6824.0
  },
  "state_complete": true
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `session_id` | string | Lưu lại cho request tiếp theo |
| `reply` | string | Tin nhắn chatbot (hiển thị cho user) |
| `is_prediction` | bool | `true` khi có kết quả dự đoán |
| `prediction.price_per_m2` | float | Giá/m² (triệu VND) |
| `prediction.total_price` | float | Tổng giá (triệu VND) |
| `state_complete` | bool | `true` sau khi đã dự đoán xong |

**Lệnh đặc biệt người dùng có thể gõ:**

| Lệnh | Tác dụng |
|------|---------|
| `ok` / `xong` / `đủ rồi` | Xác nhận và bắt đầu dự đoán |
| `xem lại` | Bot tóm tắt thông tin đã thu thập |
| `reset` | Xóa session, bắt đầu mới |
| `exit` / `quit` | Kết thúc phiên |

**Luồng hội thoại điển hình:**

```
User: "nhà riêng 80m2 quận 7"
Bot:  "Bạn vui lòng cho biết thêm số phòng ngủ không? Hoặc gõ ok!"

User: "2 phòng ngủ"
Bot:  "Thông tin đã đủ. Gõ ok để dự đoán nhé!"

User: "ok"
Bot:  "Kết quả: 85.3 triệu/m², tổng ~6.82 tỷ VND..."
```

---

## 6. Enums & Mapping

### Loại Bất động sản

| Code | Tên | Ghi chú |
|------|-----|---------|
| `0` | Căn hộ chung cư | Không hỏi số tầng, mặt tiền |
| `2` | Nhà riêng | |
| `3` | Nhà biệt thự, liền kề | |
| `4` | Nhà mặt phố | |
| `7` | Bán đất | Không hỏi phòng ngủ, số tầng |

### Quận/Huyện

| Code | Tên | Code | Tên |
|------|-----|------|-----|
| `0` | Bình Chánh | `12` | Quận 12 |
| `1` | Bình Tân | `13` | Quận 2 |
| `2` | Bình Thạnh | `14` | Quận 3 |
| `3` | Cần Giờ | `15` | Quận 4 |
| `4` | Củ Chi | `16` | Quận 5 |
| `5` | Gò Vấp | `17` | Quận 6 |
| `6` | Hóc Môn | `18` | Quận 7 |
| `7` | Nhà Bè | `19` | Quận 8 |
| `8` | Phú Nhuận | `20` | Quận 9 |
| `9` | Quận 1 | `21` | Thủ Đức |
| `10` | Quận 10 | `22` | Tân Bình |
| `11` | Quận 11 | `23` | Tân Phú |

---

## 7. Error Codes

| Code | Tình huống | Xử lý frontend |
|------|-----------|----------------|
| `200` | Thành công | — |
| `404` | Chưa có model active (chưa retrain) | Hiển thị banner "Hệ thống chưa có model. Vui lòng retrain." |
| `409` | Retrain đang chạy | Disable nút trigger, hiển thị spinner |
| `422` | Request body sai format | Kiểm tra lại input |
| `500` | Lỗi server | Hiển thị thông báo lỗi chung |

---

## 8. Gợi ý luồng Frontend

### Dashboard (trang chính)

```
Khởi động app
    ↓
GET /retrain/status
    ├── status = "running" → Hiển thị spinner "Đang retrain..."
    ├── last_run = null    → Hiển thị banner "Chưa có model, nhấn Retrain"
    └── last_run.status = "success" → Load dashboard bình thường
            ↓
    Song song gọi 4 API:
    ├── GET /eda/price-distribution   → Bar chart histogram
    ├── GET /eda/district-property-type → Heatmap/grouped bar
    ├── GET /feature-importance        → Horizontal bar chart
    └── GET /eda/scatter/version       → Kiểm tra cache version
            ↓ (nếu run_id khác cached)
        GET /eda/scatter/file → Download CSV → Scatter plot
```

### Trang Dự đoán

```
User điền form (loại BĐS, quận, diện tích, ...)
    ↓
POST /predict
    ├── predicted_price_per_m2 = null → "Model chưa sẵn sàng"
    └── Có giá → Hiển thị kết quả
```

### Trang Chatbot

```
Mount component → session_id = null

User gửi tin nhắn
    ↓
POST /chat { session_id, message }
    ↓
Lưu session_id từ response
    ├── is_prediction = false → Hiển thị reply, chờ input tiếp
    └── is_prediction = true  → Hiển thị kết quả giá + giải thích
            ↓
        state_complete = true → Hiển thị nút "Dự đoán mới" (gửi "reset")
```

### Polling Retrain Status

```javascript
// Sau khi POST /retrain/trigger thành công:
const poll = setInterval(async () => {
  const { status, last_run } = await fetch('/retrain/status').then(r => r.json())
  if (status === 'idle') {
    clearInterval(poll)
    // Reload dashboard data
  }
}, 5000) // Poll mỗi 5 giây
```

### Cache Scatter File

```javascript
const cached = localStorage.getItem('scatter_run_id')
const { run_id } = await fetch('/eda/scatter/version').then(r => r.json())

if (String(run_id) !== cached) {
  const csv = await fetch('/eda/scatter/file').then(r => r.text())
  // Parse và render scatter plot
  localStorage.setItem('scatter_run_id', run_id)
}
```

---

## Môi trường biến

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| `OPENAI_KEY` | ✅ | OpenAI API key (cho chatbot + giải thích giá) |
| `GOONG_API_KEY` | ✅ | Goong geocoding (địa chỉ → tọa độ, dùng trong chatbot) |
| `SQLALCHEMY_DATABASE_URL` | ❌ | Mặc định SQLite. Ví dụ MySQL: `mysql+pymysql://user:pass@host/db` |
| `OPENAI_MODEL` | ❌ | Mặc định `gpt-4o-mini` |
