# Context Dự Án: Web API Dự Đoán Giá BĐS TP.HCM

## 1. Tổng quan dự án

Hệ thống gồm 3 thành phần chính:
1. **Chatbot CLI** (`test.py`) — đã hoàn thành, dùng OpenAI + RandomForest để hỏi thông tin BĐS và dự đoán giá
2. **Web API** (`src/web/`) — FastAPI backend, đang xây dựng, gồm: predict, EDA charts, retrain, chatbot web
3. **Retrain pipeline** (`src/web/app/retrain/`) — pipeline làm sạch dữ liệu và train lại model, đang hoàn thiện

---

## 2. Cấu trúc thư mục

```
src/web/
├── main.py                          ✅ DONE — FastAPI app, gọi init_db() lúc startup
├── app/
│   ├── config/__init__.py           ✅ DONE — BASE_DIR = src/web/app/
│   ├── api/
│   │   ├── api_router.py            ⚠️  CHỈ CÓ predict — cần thêm các router khác
│   │   ├── api_predict.py           ✅ DONE — POST /predict
│   │   ├── api_eda.py               ❌ RỖNG — cần implement
│   │   ├── api_feature_important.py ❌ RỖNG — cần implement
│   │   ├── api_gpt.py               ❌ RỖNG — chatbot endpoint, cần implement
│   ├── db/
│   │   ├── __init__.py              ✅ DONE
│   │   ├── database.py              ✅ DONE — SQLite, SessionLocal, init_db()
│   │   └── models.py                ✅ DONE — ORM models đầy đủ (xem mục 4)
│   ├── model/
│   │   └── Schema.py                ❌ RỖNG — Pydantic schemas, cần implement
│   ├── service/
│   │   ├── predict_service.py       ⚠️  CÓ BUG — xem mục 6
│   │   └── goong.py                 ✅ DONE — geocoding địa chỉ VN → lat/lon
│   ├── retrain/
│   │   └── retrain.py               ✅ DONE — pipeline clean + train (xem mục 5)
│   └── data/
│       └── data.csv                 — training data, ~24,880 dòng
├── media/
│   ├── model_ai/                    — file .pkl các model đã train
│   │   ├── RandomForestRegressor.pkl  (model đang dùng)
│   │   ├── Best_RandomForestRegressor.pkl
│   │   └── ... (DecisionTree, KNN, LinearReg, XGB, house_price_model)
│   └── data/
│       └── data.csv                 — bản sao data dùng cho media serving
```

---

## 3. Tech Stack

- **Framework**: FastAPI + Uvicorn (port 8000)
- **Database**: SQLite (`app/db/app.db`) via SQLAlchemy 2.x (Mapped[] syntax)
- **ML**: scikit-learn RandomForestRegressor, joblib
- **LLM**: OpenAI API (`gpt-4o-mini` mặc định)
- **Geocoding**: Goong API (địa chỉ VN → lat/lon)
- **Python**: 3.11+

**Biến môi trường (`.env`):**
```
OPENAI_KEY=sk-...
GOONG_API_KEY=...
OPENAI_MODEL=gpt-4o-mini   # tuỳ chọn
```

---

## 4. Database Schema (`app/db/models.py`)

### Enums (Python, không lưu DB)

```python
class District(Enum):       # 24 quận TP.HCM — value = (code: int, label: str)
class RealEstateType(Enum): # 5 loại BĐS — value = (code: int, label: str)
```

Mapping:
- `District.BINH_CHANH = (0, 'bình chánh')` ... `District.TAN_PHU = (23, 'tân phú')`
- `RealEstateType.CAN_HO_CHUNG_CU = (0, 'căn hộ chung cư')`
- `RealEstateType.NHA_RIENG = (2, 'nhà riêng')`
- `RealEstateType.NHA_BIET_THU = (3, 'nhà biệt thự, liền kề')`
- `RealEstateType.NHA_MAT_PHO = (4, 'nhà mặt phố')`
- `RealEstateType.BAN_DAT = (7, 'bán đất')`

Cả hai enum có method: `.code`, `.label`, `.from_code(int)`, `.from_label(str)`

### ORM Tables

```python
class TrainingRun(Base):
    id, triggered_at, status,         # running|success|failed|skipped
    skip_reason, total_rows, new_rows,
    duration_sec, model_replaced, model_path
    # relationships: metrics (1-1), feature_importances (1-n),
    #                price_distributions (1-n), district_price_stats (1-n),
    #                activation (1-1)

class ModelMetrics(Base):
    id, run_id (FK),
    rmse, mae, r2,           # model mới
    prev_rmse, prev_mae, prev_r2  # model cũ để so sánh

class FeatureImportance(Base):
    id, run_id (FK), feature_name, importance

class PriceDistribution(Base):
    id, run_id (FK),
    min_range, max_range,    # float, đơn vị triệu VND/m²
    price_range,             # label vd: "0-30", "30-50", ..., "130+"
    samples_count

class DistrictPriceStats(Base):
    id, run_id (FK),
    district_code (int),     # District.code
    property_code (int),     # RealEstateType.code
    median_price (float),    # triệu VND/m²
    sample_count (int)       # nhóm < 10 bị lọc ở service layer
    # Index unique: (district_code, property_code, run_id)
    # properties: .district → District, .real_estate_type → RealEstateType

class PathActivation(Base):
    id, run_id (FK, unique),
    path_model,              # đường dẫn .pkl đang dùng
    path_scatter,            # đường dẫn scatter CSV
    path_data,               # đường dẫn data.csv đã dùng train
    is_active (bool)         # CHỈ 1 record is_active=True tại mọi thời điểm
    # run_id dùng làm VERSION cho scatter file (xem mục API EDA)
```

---

## 5. Retrain Pipeline (`app/retrain/retrain.py`) — ĐÃ HOÀN THÀNH

**Class `RetrainService(file_path, db_session)`**

`__init__`:
- Đọc CSV, chia tọa độ `/1e9` (data.csv lưu tọa độ ×10⁹), tính `cách trung tâm` (haversine), drop cột `giá`

`retrain_model()` → trả về dict:
```python
{
    "pipeline": sklearn.Pipeline,        # imputer + RandomForest
    "importance": pd.Series,             # feature_name → importance, sorted desc
    "data_price_distribution": dict,     # {"0-30": n, "30-50": n, ..., "130+": n}
    "data_scatter_plot": pd.DataFrame,   # cols: tọa độ x, tọa độ y, diện tích, giá/m2
    "data_district_stats": pd.DataFrame, # cols: district_code, property_code, median_price, sample_count
    "rmse": float,
    "mae": float,
    "r2": float,
}
```

**Thứ tự xử lý trong pipeline:**
1. Dedup
2. Filter loại BĐS (giữ code: 0,2,3,4,7 — bỏ 1,5,6,8,9)
3. Filter tọa độ ngoài HCM (10.38–11.10 lat, 106.1–106.8 lon)
4. Filter pháp lý (bỏ ==2 và null)
5. Filter outlier: phòng ngủ<11, mặt tiền≤30, giá/m2≤500, diện tích 15–500
6. Tính chart data (price_distribution, scatter, district_stats)
7. StratifiedShuffleSplit 80/20 theo khoảng cách trung tâm
8. Fill median (tính từ train_set, áp cho cả test_set)

**Model params (best từ GridSearch trước đó):**
`n_estimators=300, max_depth=30, min_samples_split=2, min_samples_leaf=1`

**Target**: `log(giá/m2)` → predict → `exp()` để ra triệu VND/m²

**Features (X_train columns):**
`loại nhà đất, địa chỉ, diện tích, mặt tiền, phòng ngủ, tọa độ x, tọa độ y, số tầng, cách trung tâm`

---

## 6. Bug Đã Biết — `predict_service.py`

`predict_service.py` hiện load `model_ai/RandomForestRegressor.pkl` — model này được train từ notebook với tọa độ ×10⁹ (chưa chuẩn hóa). Sau khi retrain bằng `retrain.py` (tọa độ đã /1e9), **cần update `predict_service.py` để load model mới từ `PathActivation`** thay vì hardcode path.

Hiện tại `predict_service.py` có thêm bug nhỏ:
- Dùng `model.predict()` thay vì `pipeline.predict()` → NaN không được impute

---

## 7. API Hiện Có

### POST /predict
Input (dict):
```json
{
  "loại nhà đất": 0,
  "địa chỉ": 18,
  "diện tích": 70.0,
  "mặt tiền": null,
  "phòng ngủ": 2,
  "tọa độ x": 10.75,
  "tọa độ y": 106.70,
  "số tầng": null
}
```
Output:
```json
{ "predicted_price_per_m2": 51.2, "predicted_total_price": 3584.0 }
```

---

## 8. Việc Cần Làm (theo thứ tự)

### BƯỚC 1 — `app/retrain/retrain_service.py` (orchestrator)

File mới, wrap `RetrainService` và xử lý:

```python
class RetrainOrchestrator:
    def __init__(self, db_session): ...

    def check_new_rows(self, data_path: str) -> int:
        """
        So sánh tổng dòng data.csv hiện tại với total_rows của TrainingRun mới nhất.
        Trả về số dòng mới. Nếu chưa có run nào → trả về tổng dòng.
        """

    def run(self, data_path: str) -> dict:
        """
        1. check_new_rows → nếu < 100: lưu TrainingRun(status='skipped'), return
        2. Tạo TrainingRun(status='running'), commit để có run.id
        3. Gọi RetrainService(data_path, db_session).retrain_model() → result
        4. Load model cũ từ PathActivation(is_active=True).path_model → so sánh RMSE
        5. Nếu model mới tốt hơn (rmse thấp hơn):
             - Lưu model .pkl: media/model_ai/rf_{timestamp}.pkl
             - Lưu scatter CSV: media/scatter/scatter_{timestamp}.csv (sample 2000 dòng)
             - Tạo PathActivation mới (is_active=True), set record cũ is_active=False
             - model_replaced = True
           Nếu kém hơn: model_replaced = False
        6. Lưu ModelMetrics (rmse, mae, r2, prev_rmse, prev_mae, prev_r2)
        7. Lưu FeatureImportance (nhiều records, 1 per feature)
        8. Lưu PriceDistribution (nhiều records, 1 per bin)
        9. Lưu DistrictPriceStats (nhiều records, 1 per district×property_type)
        10. Update TrainingRun: status='success', duration_sec, model_replaced, total_rows, new_rows
        11. Trả về summary dict
        """
```

**Lưu ý quan trọng:**
- Scatter file sample 2000 dòng ngẫu nhiên (random_state=42) trước khi lưu
- `path_model`, `path_scatter`, `path_data` lưu dạng relative path từ `BASE_DIR`
- Nếu chưa có model cũ (lần retrain đầu tiên) → bỏ qua bước so sánh, luôn replace
- Wrap toàn bộ trong try/except → nếu lỗi: update TrainingRun(status='failed')

---

### BƯỚC 2 — Fix `app/service/predict_service.py`

Thay vì hardcode path, load model từ DB:

```python
def _load_active_model(db_session):
    """
    Query PathActivation WHERE is_active=True.
    Load pipeline từ path_model.
    Trả về (pipeline, median_series).
    """
```

Sửa `predict()` dùng `pipeline.predict()` thay vì `model.predict()`.

Vì model mới train với tọa độ chuẩn (đã /1e9), Goong trả về tọa độ chuẩn → không cần thêm gì.

---

### BƯỚC 3 — `app/api/api_retrain.py`

```python
router = APIRouter(prefix="/retrain", tags=["retrain"])

# Kích hoạt retrain — chạy background để không block request
@router.post("/trigger")
def trigger_retrain(background_tasks: BackgroundTasks, db=Depends(get_db)):
    """
    Kiểm tra xem có đang running không (query TrainingRun WHERE status='running').
    Nếu có → return 409 Conflict.
    Nếu không → thêm RetrainOrchestrator.run() vào BackgroundTasks.
    Return: { "message": "Retrain đã được kích hoạt" }
    """

@router.get("/status")
def get_status(db=Depends(get_db)):
    """
    Query TrainingRun ORDER BY triggered_at DESC LIMIT 1.
    Return: { "status": "idle|running", "last_run": { id, triggered_at, status, new_rows, model_replaced } }
    """

@router.get("/history")
def get_history(page: int = 1, size: int = 10, db=Depends(get_db)):
    """
    Query TrainingRun ORDER BY triggered_at DESC, phân trang.
    Join ModelMetrics.
    Return list runs với metrics.
    """

@router.get("/metrics/trend")
def get_metrics_trend(db=Depends(get_db)):
    """
    Query tất cả TrainingRun WHERE status='success' JOIN ModelMetrics.
    Return: { "runs": [{ run_id, date, rmse, mae, r2 }] }  ← dùng vẽ line chart
    """
```

---

### BƯỚC 4 — `app/api/api_eda.py`

```python
router = APIRouter(prefix="/eda", tags=["eda"])

@router.get("/price-distribution")
def price_distribution(db=Depends(get_db)):
    """
    Query PathActivation WHERE is_active=True → lấy run_id.
    Query PriceDistribution WHERE run_id=run_id.
    Return: { "run_id": n, "bins": [{ "label": "0-30", "min": 0, "max": 30, "count": n }] }
    """

@router.get("/district-property-type")
def district_property_type(db=Depends(get_db)):
    """
    Query PathActivation WHERE is_active=True → run_id.
    Query DistrictPriceStats WHERE run_id=run_id.
    Map district_code → District.label, property_code → RealEstateType.label.
    Return: { "run_id": n, "data": [{ "district": "quận 7", "property_type": "nhà riêng", "median_price": 85.2, "sample_count": 120 }] }
    """

@router.get("/scatter/version")
def scatter_version(db=Depends(get_db)):
    """
    Query PathActivation WHERE is_active=True.
    Return: { "run_id": n, "updated_at": "2026-04-08T..." }
    Frontend dùng run_id để check xem có cần download file mới không.
    """

@router.get("/scatter/file")
def scatter_file(db=Depends(get_db)):
    """
    Query PathActivation WHERE is_active=True → path_scatter.
    Return: FileResponse(path_scatter, media_type="text/csv", filename="scatter.csv")
    Headers: Cache-Control: max-age=86400
    """
```

---

### BƯỚC 5 — `app/api/api_feature_important.py`

```python
router = APIRouter(tags=["eda"])

@router.get("/feature-importance")
def feature_importance(db=Depends(get_db)):
    """
    Query PathActivation WHERE is_active=True → run_id.
    Query FeatureImportance WHERE run_id=run_id ORDER BY importance DESC.
    Return: {
        "run_id": n,
        "features": [{ "name": "cách trung tâm", "importance": 0.31 }]
    }
    """
```

---

### BƯỚC 6 — `app/model/Schema.py` (Pydantic)

```python
class PredictInput(BaseModel):
    loai_nha_dat: int
    dia_chi: int
    dien_tich: float
    mat_tien: float | None = None
    phong_ngu: int | None = None
    toa_do_x: float
    toa_do_y: float
    so_tang: int | None = None

class PredictOutput(BaseModel):
    predicted_price_per_m2: float
    predicted_total_price: float

class TrainingRunSchema(BaseModel):
    id: int
    triggered_at: datetime
    status: str
    new_rows: int | None
    total_rows: int | None
    duration_sec: float | None
    model_replaced: bool | None
    model_class Config: from_attributes = True

class MetricsTrendItem(BaseModel):
    run_id: int
    date: datetime
    rmse: float
    mae: float
    r2: float
```

---

### BƯỚC 7 — `app/api/api_gpt.py` (Chatbot Web)

Port logic từ `test.py` (CLI) sang FastAPI. Sự khác biệt chính:
- CLI dùng `input()` → API nhận message qua POST body
- State (`ChatState`) phải persist giữa các request → dùng **session_id** (UUID)
- Lưu state in-memory: `dict[session_id → ChatState]` (đủ dùng cho scale nhỏ)

```python
# In-memory store
_sessions: dict[str, ChatState] = {}

@router.post("/chat")
def chat(body: ChatRequest, db=Depends(get_db)):
    """
    ChatRequest: { session_id: str | None, message: str }
    
    1. Nếu session_id là None hoặc không tồn tại → tạo session mới, init ChatState
    2. Xử lý message (giống test.py):
       a. Nhận biết lệnh đặc biệt: reset, xem lại, exit
       b. _is_done_signal() → force_done
       c. llm_extract() → trích xuất structured data
       d. _extract_from_text() → Python regex extraction
       e. Merge + update ChatState
       f. Goong geocoding nếu có địa chỉ mới
       g. Nếu done → predict → _explain_prediction()
       h. Nếu chưa done → llm_converse() → câu hỏi tiếp theo
    3. Return: {
         session_id: str,
         reply: str,
         is_prediction: bool,
         prediction: { price_per_m2, total_price } | None,
         state_complete: bool
       }
    """
```

**Lưu ý chatbot:**
- `llm_extract()` và `_extract_from_text()` copy nguyên từ `test.py`
- `llm_converse()` copy nguyên từ `test.py`
- `_explain_prediction()` copy nguyên từ `test.py`
- Thay `_predict()` bằng gọi `predict_service.predict()`
- `ChatState` dataclass giữ nguyên từ `test.py`
- Session in-memory: nếu idle quá 30 phút → xóa (dùng `last_activity` timestamp)

**File `prompt.txt`** (dùng cho `llm_extract`):
- Đang ở root project (`d:/my_project/crawl_data/prompt.txt`)
- Cần copy vào `src/web/app/` hoặc dùng absolute path

---

### BƯỚC 8 — Update `app/api/api_router.py`

```python
from app.api import api_predict, api_retrain, api_eda, api_feature_important, api_gpt

router = APIRouter()
router.include_router(api_predict.router, tags=["predict"])
router.include_router(api_retrain.router)
router.include_router(api_eda.router)
router.include_router(api_feature_important.router)
router.include_router(api_gpt.router, tags=["chat"])
```

---

## 9. Thứ Tự Thực Hiện Được Khuyến Nghị

```
1. retrain_service.py   → chạy retrain 1 lần để có data trong DB
2. api_retrain.py       → expose trigger + history
3. Fix predict_service.py → load model từ DB thay vì hardcode
4. api_eda.py           → đọc từ DB
5. api_feature_important.py
6. Schema.py            → Pydantic models
7. api_gpt.py           → chatbot
8. api_router.py        → wire tất cả
```

---

## 10. Lưu Ý Quan Trọng Không Được Bỏ Qua

1. **Tọa độ trong data.csv bị scale ×10⁹** — phải chia `/1e9` trước khi dùng. Đã fix trong `retrain.py`. Model sau khi retrain sẽ dùng tọa độ thực (~10.8, ~106.6). Goong API trả về tọa độ thực → compatible.

2. **Model cũ** (`media/model_ai/RandomForestRegressor.pkl`) được train với tọa độ ×10⁹ → **không dùng được** sau khi retrain với tọa độ chuẩn. Phải chạy retrain ít nhất 1 lần để có model mới trước khi test predict.

3. **PathActivation chỉ có 1 record `is_active=True`** — service layer phải đảm bảo: khi activate record mới, set tất cả record cũ `is_active=False` trong cùng 1 transaction.

4. **Scatter file** lưu ở `media/scatter/scatter_{timestamp}.csv`, sample 2000 dòng. Frontend check version qua `GET /eda/scatter/version` → so sánh `run_id` với cached → nếu khác gọi `GET /eda/scatter/file`.

5. **`BASE_DIR`** = `src/web/app/` (từ `config/__init__.py`). Path cho media nên là relative từ đây hoặc dùng absolute.

6. **Chatbot session** lưu in-memory, không cần DB. Session key = UUID string do frontend tạo hoặc backend tạo lần đầu.

7. **`DistrictPriceStats` lọc nhóm < 10 mẫu** trong `__compute_district_stats()` của `retrain.py` — đã implement. Khi query API chỉ cần đọc từ DB, không cần filter thêm.
