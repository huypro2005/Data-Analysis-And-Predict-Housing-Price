# Chatbot Dự Đoán Giá Bất Động Sản TP.HCM

Chatbot CLI tương tác bằng tiếng Việt, dùng OpenAI để hiểu ngôn ngữ tự nhiên và mô hình RandomForest để dự đoán giá BĐS.

---

## Mục lục

1. [Yêu cầu môi trường](#1-yêu-cầu-môi-trường)
2. [Cách chạy](#2-cách-chạy)
3. [Kiến trúc hệ thống](#3-kiến-trúc-hệ-thống)
4. [Luồng hội thoại](#4-luồng-hội-thoại)
5. [Các trường thông tin](#5-các-trường-thông-tin)
6. [Lệnh đặc biệt](#6-lệnh-đặc-biệt)
7. [Kịch bản mẫu](#7-kịch-bản-mẫu)
8. [Giới hạn hệ thống](#8-giới-hạn-hệ-thống)
9. [Cấu hình nâng cao](#9-cấu-hình-nâng-cao)

---

## 1. Yêu cầu môi trường

### Biến môi trường (file `.env`)

```env
OPENAI_KEY=sk-proj-...          # Bắt buộc — OpenAI API key
GOONG_API_KEY=...               # Bắt buộc — Goong geocoding (địa chỉ VN → tọa độ)
OPENAI_MODEL=gpt-4o-mini        # Tuỳ chọn — mặc định: gpt-4o-mini
MODEL_PATH=./models/RandomForestRegressor.pkl  # Tuỳ chọn — đường dẫn model
```

### Thư viện Python

```bash
pip install openai python-dotenv joblib numpy pandas scikit-learn requests
```

### File model

Đặt file `.pkl` tại `./models/RandomForestRegressor.pkl` (hoặc chỉnh `MODEL_PATH`).  
Model phải là `sklearn.pipeline.Pipeline` có 2 bước: `imputer` (SimpleImputer) và `model` (RandomForestRegressor).

---

## 2. Cách chạy

```bash
# Kích hoạt môi trường ảo
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# Chạy chatbot
python test.py
```

---

## 3. Kiến trúc hệ thống

```
Người dùng nhập text
        │
        ├─── Lệnh đặc biệt? ──────────────────────► xem lại / reset / exit
        │
        ├─── "ok / xong / đủ rồi"? ───────────────► Bỏ qua LLM, tiến hành dự đoán
        │    (Python-level detection)
        │
        ├─── Call 1: llm_extract()               ┐
        │    JSON Schema — trích xuất dữ liệu    │  Hai call song song
        │    [prompt.txt]                        │  cho mỗi lượt nhập
        │                                        │
        ├─── Python extraction (regex+keyword)   ┘
        │    Bổ sung khi LLM thiếu sót
        │
        ├─── Cập nhật ChatState
        │
        ├─── Goong API geocoding
        │    địa chỉ text → (latitude, longitude)
        │
        ├─── Call 2: llm_converse()
        │    Plain text — sinh câu hỏi tiếp theo
        │    dựa trên state hiện tại
        │
        └─── Đủ thông tin? ────────────────────► ML Model dự đoán giá
                                                        │
                                                        ▼
                                               Call 3: _explain_prediction()
                                               Giải thích lý do giá
```

### Các thành phần chính

| File | Vai trò |
|------|---------|
| `test.py` | Entry point, toàn bộ logic chatbot |
| `prompt.txt` | System prompt cho `llm_extract` (extraction-only) |
| `goong.py` | Geocoding địa chỉ tiếng Việt → tọa độ |
| `models/RandomForestRegressor.pkl` | Mô hình dự đoán giá đã train |

---

## 4. Luồng hội thoại

### Giai đoạn 1 — Thu thập thông tin bắt buộc
Bot hỏi lần lượt cho đến khi có đủ 3 trường: **loại nhà đất**, **địa chỉ/quận**, **diện tích**.

### Giai đoạn 2 — Xác nhận và hỏi optional
Khi đủ thông tin bắt buộc, bot:
1. Hiển thị tóm tắt thông tin đang có
2. Hỏi thêm thông tin tuỳ chọn **phù hợp với loại BĐS**:

| Loại BĐS | Thông tin optional được hỏi |
|----------|----------------------------|
| Căn hộ chung cư | Số phòng ngủ |
| Bán đất | Mặt tiền, số tầng |
| Nhà riêng / mặt phố / biệt thự | Phòng ngủ, mặt tiền, số tầng |

### Giai đoạn 3 — Dự đoán
Khi user xác nhận (`ok` / `xong` / ...), bot:
1. Gọi Goong API lấy tọa độ (nếu chưa có)
2. Tính khoảng cách đến trung tâm TP.HCM (Nhà thờ Đức Bà)
3. Gọi RandomForest model
4. Hiển thị kết quả + giải thích AI

### Giai đoạn 4 — Sau dự đoán
User có thể:
- Sửa thông tin rồi gõ `ok` để dự đoán lại
- Gõ `reset` để bắt đầu BĐS mới

---

## 5. Các trường thông tin

### Bắt buộc

| Trường | Mô tả | Ví dụ nhập |
|--------|-------|-----------|
| Loại nhà đất | Loại BĐS | "nhà riêng", "căn hộ chung cư", "bán đất" |
| Địa chỉ | Tên đường hoặc khu vực + quận | "đường Nguyễn Trãi, Quận 5" |
| Quận/huyện | Trong 24 quận/huyện TP.HCM | "Quận 7", "Thủ Đức", "Bình Tân" |
| Diện tích | Diện tích m² | "80m2", "80 mét vuông" |

### Tuỳ chọn (cải thiện độ chính xác)

| Trường | Mô tả | Ví dụ nhập |
|--------|-------|-----------|
| Số tầng | Số tầng của nhà | "3 tầng", "3 lầu" |
| Số phòng ngủ | Số phòng ngủ | "2 phòng ngủ", "2PN" |
| Mặt tiền | Chiều rộng mặt tiền (m) | "mặt tiền 5m", "ngang 4m" |

### Tự động tính toán (không cần nhập)

| Trường | Cách tính |
|--------|-----------|
| Tọa độ (lat, lon) | Goong API geocoding từ địa chỉ |
| Khoảng cách trung tâm | Haversine từ tọa độ đến Nhà thờ Đức Bà |

### Giá trị mặc định theo loại BĐS

| Loại | Trường tự điền | Lý do |
|------|---------------|-------|
| Căn hộ chung cư | Số tầng, mặt tiền | Không áp dụng cho căn hộ |
| Bán đất | Số tầng, phòng ngủ | Không áp dụng cho đất thô |

---

## 6. Lệnh đặc biệt

| Lệnh | Tác dụng |
|------|---------|
| `xem lại` | Hiển thị toàn bộ thông tin đang có trong phiên |
| `reset` | Xoá toàn bộ thông tin, bắt đầu lại |
| `exit` / `quit` / `bye` | Thoát chatbot |
| `ok` / `xong` / `đủ rồi` | Xác nhận đủ thông tin, tiến hành dự đoán |

**Danh sách đầy đủ từ xác nhận được nhận diện:**
`ok`, `okay`, `oke`, `xong`, `đủ`, `đủ rồi`, `đã đủ`, `được rồi`, `tiến hành`, `dự đoán đi`, `xác nhận`, `chốt`  
*(cả phiên bản có dấu và không dấu)*

---

## 7. Kịch bản mẫu

### Kịch bản 1 — Nhập nhiều thông tin cùng lúc

```
Bot: Chào bạn! Mình sẽ hỏi vài thông tin để dự đoán giá BĐS.

You: căn hộ chung cư 70m2 ở bình tân

Bot: Bạn đã cung cấp thông tin về căn hộ chung cư tại Bình Tân, TP.HCM với
     diện tích 70 m². Bạn vui lòng cho biết số phòng ngủ nhé?
     Hoặc gõ ok để dự đoán ngay!

You: 2 phòng ngủ

Bot: Đã có đủ thông tin. Gõ ok để tiến hành dự đoán nhé!

You: ok

Bot: Kết quả dự đoán:
     - Giá/m²: 51.0 triệu VND/m²
     - Tổng giá (ước tính): 3.57 tỷ VND

     Lý do giá ở mức này:
     - Vị trí: Bình Tân cách trung tâm ~10km, khu vực đang phát triển...
     - Loại BĐS: Căn hộ chung cư phù hợp gia đình trẻ...
     - Đặc điểm: 2 phòng ngủ, 70m² là thông số phổ biến khu vực này...
```

### Kịch bản 2 — Nhập từng bước

```
You: nhà riêng quận 1
Bot: Bạn có thể cho mình biết diện tích (m²) không?

You: 80m2
Bot: Thông tin bạn cung cấp đã đầy đủ. Bạn có muốn thêm số phòng ngủ,
     mặt tiền, số tầng không? Hoặc gõ ok để dự đoán ngay!

You: 3 tầng, mặt tiền 4m
Bot: Bạn muốn thêm gì nữa không, hay gõ ok để dự đoán?

You: ok
Bot: Kết quả dự đoán: ...
```

### Kịch bản 3 — Sửa thông tin sau dự đoán

```
[Sau khi đã dự đoán]
Bot: Bạn muốn làm gì tiếp theo?
     • Sửa thông tin: nói trực tiếp, ví dụ 'sửa phòng ngủ thành 3'
     • Dự đoán lại sau khi sửa: gõ 'ok'
     • Bắt đầu BĐS mới: gõ 'reset'

You: đổi diện tích 100m2
Bot: [Cập nhật diện tích và hỏi xác nhận]

You: ok
Bot: Kết quả dự đoán: [giá mới với diện tích 100m²]
```

### Kịch bản 4 — Địa chỉ không rõ ràng

```
You: nhà riêng 80m2, cách trung tâm 10km

Bot: Địa chỉ bạn cung cấp chưa đủ cụ thể để xác định vị trí.
     Bạn có thể cho mình biết tên đường hoặc quận/huyện không?
     Ví dụ: "đường Nguyễn Trãi, Quận 5" hoặc "Quận 7".

You: quận 7
Bot: [Tiếp tục hội thoại với địa chỉ Quận 7]
```

---

## 8. Giới hạn hệ thống

| Giới hạn | Chi tiết |
|----------|---------|
| **Phạm vi địa lý** | Chỉ hỗ trợ 24 quận/huyện TP.HCM |
| **Loại BĐS** | 5 loại: căn hộ chung cư, nhà riêng, nhà biệt thự/liền kề, nhà mặt phố, bán đất |
| **Độ chính xác** | Dự đoán dựa trên dữ liệu ~20,000 tin đăng crawl từ batdongsan.com.vn |
| **Kết quả** | Là ước tính tham khảo, không phải giá giao dịch thực tế |
| **Ngôn ngữ** | Tiếng Việt (có dấu và không dấu đều được) |
| **Giao diện** | CLI (command-line), không có giao diện web |

---

## 9. Cấu hình nâng cao

### Đổi model

```env
MODEL_PATH=./models/Best_RandomForestRegressor.pkl
```

### Đổi OpenAI model

```env
OPENAI_MODEL=gpt-4o   # Chính xác hơn nhưng tốn kém hơn
```

### Cấu trúc features của model

| Feature | Mô tả | Đơn vị |
|---------|-------|--------|
| loại nhà đất | Mã loại BĐS (0–9) | integer |
| địa chỉ | Mã quận/huyện (0–23) | integer |
| diện tích | Diện tích | m² |
| mặt tiền | Chiều rộng mặt tiền | m |
| phòng ngủ | Số phòng ngủ | integer |
| tọa độ x | Latitude | float |
| tọa độ y | Longitude | float |
| số tầng | Số tầng | integer |
| cách trung tâm | Khoảng cách đến Nhà thờ Đức Bà | km |

**Target variable:** `giá/m²` (triệu VND/m²), log-transform khi train → `exp()` khi predict.
