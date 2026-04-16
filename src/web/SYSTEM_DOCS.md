# Hệ Thống Dự Đoán Giá Bất Động Sản TP.HCM

Backend production-like: FastAPI + ML pipeline + AI chatbot + auto-retrain.

---

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Tech stack](#2-tech-stack)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Database schema](#4-database-schema)
5. [API endpoints](#5-api-endpoints)
6. [Luồng xử lý chính](#6-luồng-xử-lý-chính)
7. [ML pipeline](#7-ml-pipeline)
8. [Chatbot](#8-chatbot)
9. [Retrain pipeline](#9-retrain-pipeline)
10. [Cấu hình & chạy](#10-cấu-hình--chạy)
11. [Trade-offs & quyết định thiết kế](#11-trade-offs--quyết-định-thiết-kế)

---

## 1. Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                       CLIENT (Frontend / CLI)                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP
┌───────────────────────────────▼─────────────────────────────────┐
│                    FastAPI Application (port 8001)              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  /predict    │  │  /chat       │  │  /retrain            │   │
│  │  POST        │  │  POST        │  │  trigger / status    │   │
│  └──────┬───────┘  └──────┬───────┘  │  history / trend     │   │
│         │                 │          └──────────┬───────────┘   │
│  ┌──────▼───────┐  ┌──────▼───────┐             │               │
│  │predict_svc   │  │  ChatState   │  ┌──────────▼───────────┐   │
│  │(load model   │  │  (in-memory  │  │  RetrainOrchestrator │   │
│  │ from DB)     │  │   sessions)  │  │  (background task)   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │              │
│  ┌──────▼─────────────────▼──────────────────────▼───────────┐  │
│  │               MYSQL DB (SQLAlchemy ORM)                   │  │
│  │  TrainingRun │ ModelMetrics │ PathActivation │ ...        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  APScheduler — weekly cron → do_retrain()               │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
         │                    │                   │
   ┌─────▼──────┐    ┌────────▼──────┐    ┌───────▼──────┐
   │  Goong API │    │  OpenAI API   │    │  Partner API │
   │ (geocoding)│    │ (LLM extract  │    │ (data crawl) │
   └────────────┘    │  + converse)  │    └──────────────┘
                     └───────────────┘
```

---

## 2. Tech stack

| Layer | Công nghệ | Lý do chọn |
|-------|-----------|-----------|
| Web framework | FastAPI + Uvicorn | Async, auto OpenAPI docs, Pydantic validation |
| Database | MySQL + SQLAlchemy 2.x (driver: pymysql) | Hỗ trợ concurrent writes, production-ready |
| ML | scikit-learn RandomForest + joblib | Đã proven trên dataset BĐS, predict nhanh |
| LLM | OpenAI gpt-4o-mini | Hiểu tiếng Việt tốt, rẻ, có structured output |
| Geocoding | Goong API | Hỗ trợ địa chỉ Việt Nam tốt hơn Google Maps |
| Scheduler | APScheduler | Nhẹ, embed trong process, không cần Redis/Celery |
| Background job | FastAPI BackgroundTasks | Đủ cho retrain (không cần Celery vì task nặng nhưng không cần retry) |
| Config | python-dotenv | Standard |

---

## 3. Cấu trúc thư mục

```
src/web/
├── main.py                      # FastAPI app, lifespan, CORS, APScheduler
├── app/
│   ├── config/__init__.py       # BASE_DIR, API_PARTNER constants
│   ├── api/
│   │   ├── api_router.py        # Wire tất cả routers
│   │   ├── api_predict.py       # POST /predict
│   │   ├── api_retrain.py       # POST /retrain/trigger, GET /retrain/status|history|metrics/trend
│   │   ├── api_eda.py           # GET /eda/price-distribution|district-property-type|scatter/*
│   │   ├── api_feature_important.py  # GET /feature-importance
│   │   └── api_gpt.py           # POST /chat (chatbot với session management)
│   ├── db/
│   │   ├── database.py          # engine, SessionLocal, init_db(), get_db()
│   │   └── models.py            # ORM: TrainingRun, ModelMetrics, FeatureImportance,
│   │                            #      PriceDistribution, DistrictPriceStats, PathActivation
│   ├── model/
│   │   └── Schema.py            # Pydantic: PredictInput/Output, TrainingRunSchema, MetricsTrendItem
│   ├── service/
│   │   ├── predict_service.py   # Load model từ PathActivation, haversine, predict()
│   │   └── goong.py             # get_coordinates_from_goong(address) → {x, y, address}
│   ├── retrain/
│   │   ├── retrain.py           # RetrainService: clean data + train pipeline
│   │   └── retrain_service.py   # RetrainOrchestrator: fetch partner data + orchestrate
│   ├── data/
│   │   └── data.csv             # Training data (~45327 dòng)
│   └── media/
│       ├── model_ai/            # .pkl files: rf_{timestamp}.pkl
│       └── scatter/             # scatter_{timestamp}.csv (sample 2000 dòng)
```

---

## 4. Database schema

```
TrainingRun (1)
    ├── (1) ModelMetrics          rmse, mae, r2, prev_rmse, prev_mae, prev_r2
    ├── (n) FeatureImportance     feature_name, importance
    ├── (n) PriceDistribution     price_range, min_range, max_range, samples_count
    ├── (n) DistrictPriceStats    district_code, property_code, median_price, sample_count
    └── (1) PathActivation        path_model, path_scatter, path_data, is_active
```

### PathActivation — Model versioning

**Invariant**: Luôn có đúng 1 record `is_active=True`. Đây là pointer đến model đang phục vụ production.

- Mỗi lần retrain thành công + model mới tốt hơn → deactivate record cũ, tạo record mới
- `run_id` dùng làm **version** cho frontend check xem có cần tải scatter file mới không
- `path_model`, `path_scatter`, `path_data` lưu relative path từ `BASE_DIR`

### Enums (Python, không lưu DB)

```python
District      # 24 quận/huyện TP.HCM — code 0..23
RealEstateType # 5 loại: căn hộ(0), nhà riêng(2), biệt thự(3), mặt phố(4), đất(7)
```

---

## 5. API endpoints

### Predict

```
POST /predict
Body: {
  "loại nhà đất": int,    # RealEstateType.code
  "địa chỉ": int,         # District.code
  "diện tích": float,     # m²
  "mặt tiền": float|null,
  "phòng ngủ": int|null,
  "tọa độ x": float,      # latitude (VD: 10.776)
  "tọa độ y": float,      # longitude (VD: 106.700)
  "số tầng": int|null
}
Response: {
  "predicted_price_per_m2": float,  # triệu VND/m²
  "predicted_total_price": float    # triệu VND
}
```

### Chatbot

```
POST /chat
Body: { "session_id": str|null, "message": str }
Response: {
  "session_id": str,
  "reply": str,
  "is_prediction": bool,
  "prediction": { "price_per_m2": float, "total_price": float } | null,
  "state_complete": bool
}
```

Session timeout: 30 phút idle. Lệnh đặc biệt: `reset`, `exit`, `ok/xong/...`

### Retrain

```
POST /retrain/trigger       # Kích hoạt retrain (background), 409 nếu đang chạy
GET  /retrain/status        # { "status": "idle|running", "last_run": {...} }
GET  /retrain/history       # Danh sách runs, phân trang, kèm metrics
GET  /retrain/metrics/trend # RMSE/MAE/R2 qua các lần train (vẽ line chart)
```

### EDA

```
GET /eda/price-distribution     # Phân phối giá/m² theo bins
GET /eda/district-property-type # Giá median theo quận × loại BĐS
GET /eda/scatter/version        # { run_id, updated_at } — frontend dùng để check cache
GET /eda/scatter/file           # FileResponse CSV (Cache-Control: max-age=86400)
GET /feature-importance         # Feature importance của model hiện tại
```

---

## 6. Luồng xử lý chính

### 6.1 Predict request

```
POST /predict
    │
    ▼
predict_service.predict(data, db)
    │
    ├─ _load_active_pipeline(db)
    │      └─ query PathActivation WHERE is_active=True
    │         └─ joblib.load(path_model)
    │         └─ extract median_series từ imputer.statistics_
    │
    ├─ handle_input(data, median_series)
    │      └─ build DataFrame 9 features
    │      └─ tính cách trung tâm (haversine)
    │      └─ fillna bằng median từ training set
    │
    └─ pipeline.predict(X) → exp() → price_per_m2, total_price
```

### 6.2 Chatbot request

```
POST /chat
    │
    ├─ Lookup/create session (in-memory dict, UUID key)
    │
    ├─ Detect lệnh đặc biệt (reset/exit)
    │
    ├─ [Song song / xử lý tuần tự]
    │      ├─ llm_extract() → JSON schema output → structured fields
    │      └─ _extract_from_text() → regex Python → backup extraction
    │         └─ merge: Python kết quả ưu tiên khi LLM miss
    │
    ├─ update ChatState (loại BĐS, địa chỉ, diện tích, ...)
    │
    ├─ Geocoding nếu có địa chỉ mới
    │      └─ Goong API → (latitude, longitude)
    │
    ├─ Nếu user_done (ok/xong/...):
    │      ├─ Validate đủ fields bắt buộc
    │      ├─ predict_service.predict()
    │      └─ _explain_prediction() → OpenAI → 3 bullets giải thích
    │
    └─ Nếu chưa xong:
           └─ llm_converse() → câu hỏi tiếp theo dựa trên state
```

### 6.3 Retrain flow

```
POST /retrain/trigger
    │
    └─ BackgroundTasks.add_task(do_retrain)
            │
            ▼
    RetrainOrchestrator.run(data_path)
            │
            ├─ request_data_from_partner()
            │      └─ GET {API_PARTNER}?start_post={last_active_run.triggered_at}
            │         └─ append rows vào data.csv (nếu count >= 100)
            │
            ├─ count < 100 → TrainingRun(status="skipped"), return
            │
            ├─ TrainingRun(status="running"), commit
            │
            ├─ RetrainService.retrain_model()
            │      └─ clean → split → train RF → evaluate
            │
            ├─ So sánh RMSE với model cũ (PathActivation.is_active=True)
            │      ├─ Tốt hơn (hoặc lần đầu):
            │      │      ├─ save rf_{timestamp}.pkl
            │      │      ├─ save scatter_{timestamp}.csv (sample 2000)
            │      │      └─ PathActivation: deactivate cũ, create mới
            │      └─ Kém hơn: không replace
            │
            ├─ Lưu ModelMetrics, FeatureImportance, PriceDistribution, DistrictPriceStats
            │
            └─ TrainingRun(status="success"), commit

    APScheduler: chạy do_retrain() mỗi 7 ngày (tự động)
```

---

## 7. ML pipeline

### Features (9 features)

| Feature | Kiểu | Mô tả |
|---------|------|-------|
| loại nhà đất | int (0-9) | Mã loại BĐS |
| địa chỉ | int (0-23) | Mã quận/huyện |
| diện tích | float | m² |
| mặt tiền | float\|NaN | Chiều rộng mặt tiền (m) |
| phòng ngủ | int\|NaN | Số phòng ngủ |
| tọa độ x | float | Latitude (chia /1e9 từ CSV raw) |
| tọa độ y | float | Longitude (chia /1e9 từ CSV raw) |
| số tầng | int\|NaN | Số tầng |
| cách trung tâm | float | Haversine đến Nhà thờ Đức Bà (km) |

### Preprocessing

- **NaN**: `SimpleImputer(strategy="median")` — median tính từ train set, áp cho cả test set (tránh data leakage)
- **Outlier filter**: phòng ngủ < 11, mặt tiền ≤ 30m, giá/m2 ≤ 500tr, diện tích 15–500m²
- **Split**: `StratifiedShuffleSplit(0.2)` theo 4 bins khoảng cách trung tâm (0-5, 5-10, 10-15, 15+km)

### Model

```python
RandomForestRegressor(
    n_estimators=300,
    max_depth=30,
    min_samples_split=2,
    min_samples_leaf=1,
    random_state=42
)
```

**Target**: `log(giá/m²)` → predict → `exp()` → triệu VND/m²  
(Log-transform giảm ảnh hưởng outlier giá, đưa distribution về gần normal)

### Coordinate convention

```
data.csv lưu: tọa độ x = latitude × 1e9  (VD: 10803384659)
              tọa độ y = longitude × 1e9  (VD: 106617524363)

retrain.py: chia /1e9 khi load → tọa độ thực
Goong API: trả về tọa độ thực → dùng trực tiếp
Partner API: coord_x = longitude, coord_y = latitude → swap khi ghi CSV
```

---

## 8. Chatbot

### ChatState fields

```python
loai_nha_dat: int|None      # Bắt buộc
dia_chi_text: str|None      # Bắt buộc (raw text)
dia_chi_code: int|None      # Bắt buộc (District.code)
dien_tich: float|None       # Bắt buộc
toa_do_x: float|None        # Bắt buộc (từ Goong)
toa_do_y: float|None        # Bắt buộc (từ Goong)
so_tang: int|None           # Optional
phong_ngu: int|None         # Optional
mat_tien: float|None        # Optional
last_geocoded_address: str  # Cache address đã geocode
auto_filled: set            # Track fields đã auto-fill theo loại BĐS
```

### Auto-fill logic

| Loại BĐS | Fields tự điền (median) |
|----------|------------------------|
| Căn hộ (0) | số tầng, mặt tiền (không áp dụng) |
| Bán đất (7) | số tầng, phòng ngủ (không áp dụng) |
| Còn lại | Không tự điền |

### Session management

- Store: `dict[session_id → SessionData]` in-memory
- Timeout: 30 phút idle (check và cleanup mỗi request)
- `session_id`: UUID, frontend tự lưu và gửi kèm mỗi request
- Không cần DB vì: state chỉ cần trong 1 conversation, không có yêu cầu persistence sau restart

---

## 9. Retrain pipeline

### Partner data ingestion

```
GET {API_PARTNER}?tab=ban&province=1&start_post={ISO_datetime}

Response:
{
  "count": int,
  "data": [
    {
      "property_type": int,    # loại BĐS
      "district": int,         # quận code
      "price": "2600.00",      # triệu VND
      "area_m2": "65.00",
      "price_per_m2": "40.00",
      "coord_x": "106.823...", # longitude
      "coord_y": "10.797...",  # latitude
      "bedrooms": 2,
      "legal_status": 1,
      "frontage": null,
      "floors": null
    }
  ]
}
```

Chỉ append vào `data.csv` khi `count >= 100` (đủ để train có ý nghĩa).

### Model replacement policy

Model mới replace model cũ khi:
1. Chưa có model nào (lần đầu tiên), **hoặc**
2. RMSE model mới < RMSE model cũ

---

## 10. Cấu hình & chạy

### Biến môi trường (`.env`)

```env
OPENAI_KEY=sk-proj-...
GOONG_API_KEY=...
OPENAI_MODEL=gpt-4o-mini        # Tuỳ chọn
API_PARTNER=https://...         # URL API đối tác
SQLALCHEMY_DATABASE_URL=sqlite:///./training_management.db  # Tuỳ chọn
```

### Chạy local

```bash
cd src/web
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### Khởi động lần đầu

```bash
# 1. Chạy server → DB tự tạo qua init_db() trong lifespan
uvicorn main:app --port 8001

# 2. Kích hoạt retrain để có model đầu tiên
curl -X POST http://localhost:8001/retrain/trigger

# 3. Theo dõi tiến trình
curl http://localhost:8001/retrain/status

# 4. Sau khi done → predict
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"loại nhà đất":0,"địa chỉ":18,"diện tích":70,"tọa độ x":10.73,"tọa độ y":106.72}'
```

### API docs

```
http://localhost:8001/docs       # Swagger UI
http://localhost:8001/redoc      # ReDoc
```

---

## 11. Trade-offs & quyết định thiết kế

### Tại sao MySQL thay vì SQLite/PostgreSQL?

MySQL hỗ trợ concurrent writes tốt hơn SQLite (không bị file lock khi nhiều request đồng thời). So với PostgreSQL thì MySQL phổ biến hơn trong stack deploy Việt Nam, dễ tìm hosting hơn. SQLAlchemy ORM abstract hóa SQL dialect — nếu cần đổi sang PostgreSQL chỉ cần thay `SQLALCHEMY_DATABASE_URL` và driver (`psycopg2` thay `pymysql`).

### Tại sao in-memory session thay vì Redis?

Chat session chỉ cần persist trong 1 conversation (30 phút). Không có yêu cầu multi-instance hay session sau restart. In-memory đơn giản hơn, không cần infrastructure thêm. Nếu scale lên nhiều instance → đổi sang Redis (chỉ cần thay `_sessions` dict bằng Redis client).

### Tại sao BackgroundTasks thay vì Celery?

Retrain là task nặng (~vài phút) nhưng chỉ xảy ra 1 lần / 7 ngày hoặc khi trigger thủ công. Không có yêu cầu retry phức tạp hay distributed workers. BackgroundTasks của FastAPI đủ dùng và không cần broker (Redis/RabbitMQ). Nếu scale → thêm Celery + Redis là bước tiếp theo rõ ràng.

### Tại sao log(giá/m²) làm target?

Phân phối giá/m² bị skewed nặng về phải (outlier căn hộ trung tâm). Log-transform đưa về gần normal → RandomForest học tốt hơn, RMSE có ý nghĩa hơn. `exp()` khi predict để ra giá thực.

### Bottleneck khi 10k users

1. **Predict**: bottleneck tại `joblib.load()` nếu gọi mỗi request → fix: cache pipeline in-memory sau khi load lần đầu
2. **Chatbot**: bottleneck tại OpenAI API latency (~1-2s/call, 2-3 calls/turn) → fix: streaming response hoặc cache LLM output cho câu hỏi tương tự
3. **DB**: SQLite bị lock khi write concurrent → fix: migrate sang PostgreSQL
4. **Session store**: in-memory không share giữa instances → fix: Redis
