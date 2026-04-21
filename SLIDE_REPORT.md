# BÁO CÁO SLIDE — ĐỒ ÁN 1
## Phân tích Dữ liệu và Xây dựng Mô hình Dự đoán Giá Bất động sản
### (Ứng dụng thực nghiệm trên nền tảng Web)

**Nhóm thực hiện:** Cao Thành Huy (23520595) · Nguyễn Thái Học (23520549)  
**CBHD:** ThS. Trần Thị Hồng Yến  
**Trường:** Đại học Công nghệ Thông tin – ĐHQG TP.HCM  
**Ngày báo cáo:** 22/04/2026

---

## TỔNG QUAN TIẾN ĐỘ

| # | Giai đoạn | Thời hạn | Trạng thái |
|---|-----------|----------|------------|
| 1 | Nghiên cứu tổng quan & định hướng | 21/01–31/01 | ✅ Hoàn thành |
| 2 | Thu thập & chuẩn hóa dữ liệu | 01/02–15/02 | ✅ Hoàn thành |
| 3 | Làm sạch & tiền xử lý dữ liệu | 16/02–05/03 | ✅ Hoàn thành |
| 4 | Phân tích dữ liệu khám phá (EDA) | 06/03–20/03 | ✅ Hoàn thành |
| 5 | Feature Engineering | 21/03–31/03 | ✅ Hoàn thành |
| 6 | Xây dựng & huấn luyện mô hình ML | 01/04–12/04 | ✅ Hoàn thành |
| 7 | Đánh giá & so sánh mô hình | 13/04–20/04 | ✅ Hoàn thành |
| 8 | Tích hợp mô hình vào hệ thống Web | 21/04–30/04 | 🔄 Đang thực hiện |
| 9 | Chatbot tư vấn BĐS (LLM + Geocoding) | 01/05–10/05 | ✅ Hoàn thành sớm |
| 10 | Cơ chế cập nhật & huấn luyện lại mô hình | 11/05–15/05 | ✅ Hoàn thành sớm |
| 11 | Hoàn thiện báo cáo đồ án | 16/05–22/05 | ⏳ Chưa bắt đầu |
| 12 | Kiểm thử & chuẩn bị bảo vệ | 23/05–30/05 | ⏳ Chưa bắt đầu |

> **Nhận xét:** Tính đến 22/04/2026, nhóm đã hoàn thành 9/12 giai đoạn (75%), hoàn thành **trước kế hoạch** ở các giai đoạn 9 và 10.

---

---

# SLIDE 1 — GIỚI THIỆU ĐỀ TÀI

## Vấn đề thực tiễn

- Thị trường BĐS TP.HCM biến động phức tạp theo vị trí, diện tích, loại hình và xu hướng thị trường
- Người mua / bán thiếu công cụ **định lượng hỗ trợ ra quyết định**
- Các nền tảng hiện tại tập trung CRM, không có phân tích dữ liệu thực sự

## Giải pháp đề xuất

Xây dựng hệ thống website thực nghiệm gồm 4 thành phần:

1. **Thu thập & Phân tích dữ liệu** — EDA trực quan, thống kê mô tả
2. **Mô hình dự đoán giá** — Random Forest, so sánh nhiều thuật toán
3. **Cơ chế retrain tự động** — Cập nhật mô hình khi có dữ liệu mới
4. **Chatbot AI** — Hỏi đáp tự nhiên, tự điền form và dự đoán giá

## Phạm vi

- Địa bàn: **Thành phố Hồ Chí Minh** (24 quận/huyện)
- Loại BĐS: Căn hộ · Nhà riêng · Biệt thự · Nhà mặt phố · Đất
- Kết quả mang tính **học thuật, tham khảo** — không thay thế định giá chuyên nghiệp

---

# SLIDE 2 — THU THẬP DỮ LIỆU

## Nguồn & Quy mô

| Chỉ số | Giá trị |
|--------|---------|
| Nguồn | Dữ liệu crawl từ sàn BĐS công khai (TP.HCM) |
| Tổng bản ghi thô | **43,000 dòng** |
| Sau loại trùng | **13,578 dòng** |
| Sau lọc (bộ sạch cuối) | **8,873 dòng** |
| Tập train | 7,098 mẫu (80%) |
| Tập test | 1,775 mẫu (20%) |

## Các thuộc tính thu thập

| Thuộc tính | Kiểu | Mô tả |
|-----------|------|-------|
| `loại nhà đất` | Categorical | Loại BĐS (5 loại) |
| `địa chỉ` | Categorical | Quận/huyện (24 quận) |
| `diện tích` | Float | m² |
| `giá/m²` | Float | **Target** — triệu VND/m² |
| `mặt tiền` | Float | Chiều rộng mặt tiền (m) |
| `phòng ngủ` | Int | Số phòng ngủ |
| `số tầng` | Int | Số tầng |
| `tọa độ x` | Float | Vĩ độ (latitude) |
| `tọa độ y` | Float | Kinh độ (longitude) |
| `pháp lý` | Categorical | Tình trạng pháp lý |

---

# SLIDE 3 — LÀM SẠCH & TIỀN XỬ LÝ DỮ LIỆU

## Pipeline tiền xử lý (10 bước)

| Bước | Hành động | Kết quả |
|------|-----------|---------|
| 1 | **Loại trùng lặp** | 36,000 → 13,578 |
| 2 | **Chuẩn hóa tọa độ** | Chia 1e9 (lỗi crawl) |
| 3 | **Loại loại BĐS ít mẫu** | Bỏ type 1, 5, 6, 8, 9 |
| 4 | **Lọc địa lý** | Chỉ giữ tọa độ trong TP.HCM (lat 10.38–11.10, lon 106.1–106.8) |
| 5 | **Lọc pháp lý** | Bỏ pháp lý = 2 hoặc NaN |
| 6 | **Xử lý giá trị thiếu** | Điền median riêng cho tập train và test |
| 7 | **Chia tập train/test** | 80/20 — Stratified theo khoảng cách đến trung tâm |
| 8 | **Loại ngoại lai** (train only) | phòng ngủ < 11, mặt tiền ≤ 30m, giá/m² ≤ 500 triệu, diện tích 15–500m² |
| 9 | **Bỏ cột không cần** | Xóa cột `giá` gốc (tránh data leakage) |
| 10 | **Log-transform target** | `y = log(giá/m²)` — chuẩn hóa phân phối lệch phải |

## Kết quả sau xử lý

- Bộ dữ liệu sạch: **8,873 mẫu** với **9 đặc trưng đầu vào**
- Phân bố giá/m² sau lọc: từ ~1 đến ~500 triệu VND/m² (median 117 triệu)

---

# SLIDE 4 — PHÂN TÍCH DỮ LIỆU KHÁM PHÁ (EDA)

## Thống kê mô tả

| Thuộc tính | Mean | Median | Min | Max |
|-----------|------|--------|-----|-----|
| giá/m² (triệu) | 150.84 | 117.33 | ~1 | ~6,300 |
| diện tích (m²) | 117.52 | 83 | 1 | 996 |
| tọa độ x (lat) | 10.77 | 10.77 | 10.38 | 11.10 |

## Các biểu đồ đã tạo (12 hình)

| Nhóm | Biểu đồ | Insight chính |
|------|---------|---------------|
| Phân phối | Histogram 10 thuộc tính | Giá có **long-tail** mạnh → cần log-transform |
| Phân phối | Long-tail giá, diện tích, khoảng cách | Xác nhận cần xử lý outlier |
| Địa lý | Scatter plot tọa độ theo giá và diện tích | BĐS đắt tập trung vùng trung tâm |
| Địa lý | Scatter so sánh tốt/xấu | Visualize rõ phân vùng giá theo địa lý |
| Phân tích | Bar chart theo khoảng cách đến trung tâm | Càng xa trung tâm, mật độ BĐS càng giảm |
| Tương quan | Correlation heatmap (12×12) | `cách trung tâm` tương quan âm mạnh với giá |
| Tương quan | Scatter matrix 6 biến | Quan hệ phi tuyến giữa area–price |
| Tương quan | Distance-to-center vs. price | Quan hệ rõ: xa → rẻ |

## Phát hiện chính từ EDA

1. **Giá phân phối lệch phải** — cần log-transform trước khi huấn luyện
2. **Khoảng cách đến trung tâm** là yếu tố địa lý quan trọng nhất
3. **Tương quan phi tuyến** — Linear Regression sẽ không phù hợp
4. **Mặt tiền, phòng ngủ, số tầng** có nhiều giá trị thiếu → cần imputation

---

# SLIDE 5 — FEATURE ENGINEERING

## Đặc trưng đã xây dựng

### Đặc trưng mới: `cách trung tâm`

Tính khoảng cách từ BĐS đến **trung tâm Sài Gòn** (Nhà thờ Đức Bà: lat 10.7769, lon 106.7009) bằng công thức **Haversine**:

```
d = 2R · arcsin(√[sin²(Δlat/2) + cos(lat₁)·cos(lat₂)·sin²(Δlon/2)])
```

Kết quả: Đặc trưng này trở thành **yếu tố quan trọng nhất** (52.64% feature importance).

### Phân vùng khoảng cách (stratification)

Chia thành 4 nhóm để đảm bảo **phân bố đồng đều** khi chia train/test:

| Nhóm | Khoảng cách |
|------|------------|
| 0 | 0–5 km (trung tâm) |
| 1 | 5–10 km |
| 2 | 10–20 km |
| 3 | > 20 km (ngoại ô) |

### Tổng bộ đặc trưng (9 features)

`loại nhà đất` · `địa chỉ` · `diện tích` · `mặt tiền` · `phòng ngủ` · `số tầng` · `tọa độ x` · `tọa độ y` · **`cách trung tâm`** *(tạo mới)*

---

# SLIDE 6 — XÂY DỰNG & SO SÁNH MÔ HÌNH

## Kiến trúc Pipeline

```
Dữ liệu đầu vào (9 features)
    ↓
SimpleImputer (median strategy)   ← Xử lý NaN còn sót lại
    ↓
Regression Model
    ↓
Dự đoán log(giá/m²)  →  exp()  →  Giá/m² (triệu VND)
```

## Kết quả so sánh 5 mô hình

| Mô hình | RMSE ↓ | MAE ↓ | R² ↑ | Nhận xét |
|---------|--------|-------|-------|---------|
| **Random Forest** ⭐ | **0.33** | **0.22** | **0.81** | Tốt nhất — mô hình chính |
| XGBoost | 0.35–0.37 | 0.23 | 0.75–0.79 | Tốt, thay thế được RF |
| Decision Tree | 0.40–0.43 | 0.27–0.29 | 0.68–0.71 | Overfitting hơn RF |
| K-Nearest Neighbors | 0.50–0.54 | 0.32–0.35 | 0.48–0.54 | Phụ thuộc mạnh vào tọa độ |
| Linear Regression | 0.55–0.59 | 0.39–0.41 | 0.38–0.45 | Kém — dữ liệu phi tuyến |

> *Metrics tính trên log-scale. RMSE = 0.33 tương đương sai số ~±39% khi quy ngược về giá thực.*

## Vì sao chọn Random Forest?

- **R² = 0.81** — giải thích được 81% biến động giá
- **Ensemble method** — giảm overfitting so với Decision Tree đơn lẻ (0.81 vs 0.71)
- **Không cần chuẩn hóa** — robust với feature scales khác nhau
- **Feature importance** — cung cấp khả năng giải thích mô hình
- **Phi tuyến** — bắt được mối quan hệ phức tạp giữa vị trí và giá

## Tinh chỉnh tham số (RandomizedSearchCV)

| Tham số | Không gian tìm kiếm | Giá trị tốt nhất |
|---------|---------------------|-----------------|
| n_estimators | 100–300 | 200 |
| max_depth | 10–None | None |
| min_samples_split | 2–10 | 2 |
| min_samples_leaf | 1–4 | 1 |

---

# SLIDE 7 — PHÂN TÍCH FEATURE IMPORTANCE

## Mức độ ảnh hưởng của từng đặc trưng

| Thứ hạng | Đặc trưng | Tầm quan trọng | Ý nghĩa |
|----------|----------|----------------|---------|
| 1 | **Cách trung tâm** | **52.64%** | Vị trí địa lý là yếu tố số 1 |
| 2 | Loại nhà đất | 16.89% | Loại BĐS ảnh hưởng lớn đến phân khúc giá |
| 3 | Tọa độ X (Latitude) | 8.05% | Thông tin địa lý bổ sung |
| 4 | Tọa độ Y (Longitude) | 6.41% | Thông tin địa lý bổ sung |
| 5 | Diện tích | 6.13% | Đặc trưng vật lý quan trọng nhất |
| 6 | Số tầng | 5.32% | Phản ánh quy mô công trình |
| 7 | Địa chỉ (Quận) | 1.82% | Cung cấp thêm context địa lý |
| 8 | Mặt tiền | 1.61% | Ảnh hưởng nhỏ hơn kỳ vọng |
| 9 | Phòng ngủ | 1.13% | Ít ảnh hưởng nhất |

## Nhận xét

- **Vị trí địa lý** (cách trung tâm + tọa độ + địa chỉ) chiếm tổng **~69%** — khẳng định "location is everything"
- **Đặc trưng vật lý** (diện tích, tầng, mặt tiền, phòng ngủ) chỉ chiếm ~15%
- **Loại BĐS** (17%) — phân khúc thị trường ảnh hưởng mạnh đến giá/m²
- Kết quả nhất quán giữa notebook.ipynb và notebook1.ipynb (cách trung tâm: 52.64% vs 52.17%)

---

# SLIDE 8 — HỆ THỐNG WEB BACKEND

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|-----------|----------|
| Web Framework | **FastAPI** (async, auto Swagger docs) |
| Database ORM | **SQLAlchemy 2.0** + SQLite/MySQL |
| ML Runtime | **scikit-learn 1.7** + joblib |
| LLM | **OpenAI SDK 2.26** (gpt-4o-mini) |
| Geocoding | **Goong Maps API** (Vietnamese maps) |
| Scheduler | **APScheduler 3.11** (weekly retrain) |
| Testing | **pytest 9.0** (66+ test cases) |

## Các nhóm API endpoint

```
POST /predict              → Dự đoán giá trực tiếp
POST /retrain/trigger      → Kích hoạt retrain thủ công
GET  /retrain/status       → Trạng thái retrain hiện tại
GET  /retrain/history      → Lịch sử các lần retrain (phân trang)
GET  /retrain/metrics/trend → Xu hướng RMSE/MAE/R² qua thời gian
GET  /eda/price-distribution       → Phân phối giá (histogram)
GET  /eda/district-property-type   → Giá trung vị theo quận × loại BĐS
GET  /eda/scatter/version          → Kiểm tra phiên bản dữ liệu scatter
GET  /eda/scatter/file             → File CSV scatter plot (tối đa 2000 điểm)
GET  /feature-importance   → Tầm quan trọng các đặc trưng
GET  /geocode              → Chuyển địa chỉ → tọa độ
POST /chat                 → Chatbot AI hội thoại
```

## Cơ sở dữ liệu (6 bảng)

```
TrainingRun ──┬── ModelMetrics        (RMSE, MAE, R²)
              ├── FeatureImportance   (9 đặc trưng × tầm quan trọng)
              ├── PriceDistribution   (7 bin giá)
              ├── DistrictPriceStats  (giá median × quận × loại)
              └── PathActivation      (đường dẫn model .pkl đang active)
```

---

# SLIDE 9 — CHATBOT AI

## Kiến trúc

Chatbot sử dụng cách tiếp cận **LLM-powered Structured Extraction** thay vì RAG truyền thống:

```
Người dùng gõ tin nhắn (tiếng Việt tự nhiên)
        ↓
LLM Extraction (OpenAI JSON Schema)  +  Regex fallback
        ↓
Cập nhật ChatState (session in-memory, timeout 30 phút)
        ↓
Auto-Geocoding (Goong API: địa chỉ → tọa độ x, y)
        ↓
Kiểm tra đủ thông tin bắt buộc?
   ├── Chưa đủ → LLM sinh câu hỏi tiếp theo
   └── Đủ + user gõ "ok" → Gọi predict service
                                ↓
                        LLM giải thích kết quả (3 điểm)
                                ↓
                        Trả về giá/m² + tổng giá
```

## Tính năng chính

| Tính năng | Chi tiết |
|----------|---------|
| **Session management** | UUID session, in-memory, timeout 30 phút |
| **LLM extraction** | Trích xuất loại BĐS, địa chỉ, diện tích, phòng ngủ, mặt tiền, số tầng |
| **Regex fallback** | Hoạt động khi không có OPENAI_KEY |
| **Auto-geocode** | Tự động gọi Goong API khi có địa chỉ mới |
| **Auto-fill medians** | Điền median cho trường optional theo loại BĐS |
| **Price explanation** | LLM sinh giải thích 3 điểm cho kết quả dự đoán |
| **Special commands** | `ok/xong` → dự đoán, `reset` → phiên mới, `xem lại` → tóm tắt |

## Ví dụ hội thoại

```
User: "nhà riêng 80m2 quận 7"
Bot:  "Thông tin đã ghi nhận: nhà riêng, 80m², Quận 7.
       Bạn có thể cho biết thêm số phòng ngủ không? (hoặc gõ ok)"

User: "2 phòng"
Bot:  "Đã cập nhật. Gõ ok để xem kết quả dự đoán!"

User: "ok"
Bot:  "Kết quả dự đoán:
       • Giá/m²: ~85.3 triệu VND/m²
       • Tổng giá ước tính: ~6.82 tỷ VND
       Lý do: (1) Quận 7 cách trung tâm ~7km, khu vực phát triển...
               (2) Nhà riêng phân khúc giá trung bình...
               (3) Diện tích 80m² phù hợp thị trường..."
```

## So sánh với kế hoạch ban đầu

| Đề cương | Thực tế | Nhận xét |
|---------|---------|---------|
| RAG + GPT base model | LLM Structured Extraction + OpenAI | Không dùng RAG (vector DB) — dùng LLM trực tiếp trích xuất thông tin và giải thích kết quả |
| Gợi ý BĐS từ database | Dự đoán giá theo input người dùng | Chatbot tập trung vào dự đoán giá, không gợi ý listing cụ thể |

---

# SLIDE 10 — CƠ CHẾ RETRAIN TỰ ĐỘNG

## Quy trình Batch Retraining

```
APScheduler (mỗi 7 ngày)  hoặc  POST /retrain/trigger
        ↓
1. Lấy dữ liệu mới từ Partner API
        ↓
2. Kiểm tra số dòng mới ≥ 100?
   └── < 100 dòng → SKIP (ghi log lý do)
        ↓
3. Thêm vào data.csv + Tạo TrainingRun (status=running)
        ↓
4. Chạy pipeline tiền xử lý + huấn luyện Random Forest
        ↓
5. Đánh giá mô hình mới: RMSE, MAE, R²
        ↓
6. So sánh với mô hình cũ
   ├── RMSE mới < RMSE cũ → Thay thế mô hình ✅
   └── RMSE mới ≥ RMSE cũ → Giữ mô hình cũ ❌
        ↓
7. Lưu .pkl + scatter CSV với timestamp
        ↓
8. Cập nhật DB: ModelMetrics, FeatureImportance,
               PriceDistribution, DistrictPriceStats, PathActivation
        ↓
9. Cập nhật TrainingRun (status=success/failed)
```

## Quản lý phiên bản

- Mỗi lần retrain tạo file `.pkl` riêng với timestamp
- Chỉ **một model active** tại một thời điểm (PathActivation)
- Lưu toàn bộ metrics và feature importance cho từng lần retrain
- API `/retrain/metrics/trend` cho phép theo dõi xu hướng chất lượng mô hình

## Ngưỡng bảo vệ

| Điều kiện | Hành động |
|----------|-----------|
| Dữ liệu mới < 100 dòng | Skip retrain, ghi `status=skipped` |
| Đang có retrain chạy | Trả về HTTP 409 (Conflict) |
| RMSE không cải thiện | Giữ mô hình cũ, lưu metrics mới để theo dõi |
| Training lỗi | Rollback DB, ghi `status=failed` |

---

# SLIDE 11 — KIỂM THỬ

## Tổng quan test suite

| File test | Số test | Phạm vi |
|-----------|---------|---------|
| test_api_gpt.py | 16 | Chatbot: extraction, session, done-signal |
| test_retrain.py | 17 | Preprocessing: outlier, binning, statistics |
| test_predict_service.py | 11 | Haversine, handle_input, predict() |
| test_api_predict.py | 8 | Endpoint /predict |
| test_retrain_orchestrator.py | 14 | Orchestration: skip/success/failure flows |
| test_api_eda.py | — | EDA endpoints |
| test_api_feature_importance.py | — | Feature importance endpoint |
| **Tổng cộng** | **66+** | |

## Hạ tầng test

- **pytest** với in-memory SQLite (cô lập từng test)
- **TestClient** FastAPI (test integration endpoint)
- **Mock pipeline** với `make_mock_pipeline()`
- **conftest.py** fixtures: DB session, client, mock training runs

## Các luồng được kiểm thử

**Chatbot:**
- Trích xuất thông tin từ tin nhắn tiếng Việt (có/không dấu)
- Nhận diện các câu xác nhận: "ok", "xong", "oke", "đủ rồi"...
- Quản lý session: tạo mới, tái sử dụng, reset, timeout

**Retrain:**
- Bộ lọc ngoại lai (outlier): phòng ngủ, mặt tiền, giá, diện tích
- Lọc địa lý, lọc pháp lý
- Phân bin giá (7 khoảng)
- Skip khi < 100 dòng mới
- So sánh và thay thế mô hình

**Prediction:**
- Dự đoán với đủ và thiếu fields optional
- Xử lý khi chưa có model active (trả null)
- Tính khoảng cách Haversine

---

# SLIDE 12 — KẾT LUẬN & TIẾN ĐỘ

## Đã đạt được

| Mục tiêu đề cương | Kết quả thực tế |
|------------------|----------------|
| Thu thập ≥ 5,000 mẫu | **36,000 mẫu** thô, **8,873 mẫu** sau xử lý |
| EDA: thống kê, trực quan hóa | **12 biểu đồ**, phân tích đầy đủ distribution/correlation/geography |
| So sánh mô hình Linear + DT + RF | **5 mô hình** so sánh (thêm XGBoost, KNN) |
| Random Forest là mô hình trọng tâm | RF đạt **R²=0.81, MAE=0.22, RMSE=0.33** |
| Feature importance | Đã thực hiện: cách trung tâm chiếm 52.64% |
| Tích hợp web API | **12 endpoints** FastAPI, Swagger docs |
| Batch retraining | Hoàn thành: ngưỡng 100 dòng, so sánh RMSE tự động |
| Chatbot | Hoàn thành: LLM extraction + Geocoding + Prediction |
| Testing | **66+ test cases** với pytest |

## Sắp làm

- Hoàn thiện tích hợp Frontend (React) ↔ Backend API
- Viết báo cáo đồ án hoàn chỉnh
- Chuẩn bị demo end-to-end cho buổi bảo vệ

## Hạn chế & Hướng phát triển

| Hạn chế hiện tại | Hướng phát triển |
|-----------------|-----------------|
| Chatbot không dùng RAG thực sự | Tích hợp vector DB để gợi ý BĐS thực tế |
| RF (0.81) — còn sai số ~39% | Thử XGBoost tuned, LightGBM |
| Chưa có feature thời gian | Bổ sung thời điểm đăng bán, trend giá |
| Không có auth API | Thêm JWT authentication |
| Chỉ TP.HCM | Mở rộng sang Hà Nội, Đà Nẵng |

---

## PHỤ LỤC — SỐ LIỆU KỸ THUẬT

### Môi trường & Công nghệ

| Thành phần | Phiên bản |
|-----------|-----------|
| Python | 3.11+ |
| FastAPI | 0.135.1 |
| scikit-learn | 1.7.0 |
| pandas | 3.0.1 |
| numpy | 2.4.2 |
| SQLAlchemy | 2.0.49 |
| openai | 2.26.0 |
| APScheduler | 3.11.2 |
| pytest | 9.0.3 |

### Cấu hình mô hình Random Forest

```python
Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("model", RandomForestRegressor(
        n_estimators=200,
        random_state=42
    ))
])
```

### Phân phối giá theo bin (7 khoảng)

| Khoảng | Label |
|--------|-------|
| 0–30 triệu/m² | Giá rẻ |
| 30–50 triệu/m² | Trung bình thấp |
| 50–70 triệu/m² | Trung bình |
| 70–90 triệu/m² | Trung bình cao |
| 90–110 triệu/m² | Cao |
| 110–130 triệu/m² | Rất cao |
| 130+ triệu/m² | Cao cấp |

### Mã hóa dữ liệu

**Loại BĐS:**  
0=Căn hộ · 2=Nhà riêng · 3=Biệt thự/Liền kề · 4=Nhà mặt phố · 7=Đất

**Quận/Huyện (24 quận):**  
0=Bình Chánh · 1=Bình Tân · 2=Bình Thạnh · 3=Cần Giờ · 4=Củ Chi · 5=Gò Vấp · 6=Hóc Môn · 7=Nhà Bè · 8=Phú Nhuận · 9=Q.1 · 10=Q.10 · 11=Q.11 · 12=Q.12 · 13=Q.2 · 14=Q.3 · 15=Q.4 · 16=Q.5 · 17=Q.6 · 18=Q.7 · 19=Q.8 · 20=Q.9 · 21=Thủ Đức · 22=Tân Bình · 23=Tân Phú
