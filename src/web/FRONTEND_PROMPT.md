# Prompt: Xây dựng Frontend Hệ thống Dự đoán Giá BĐS TP.HCM

## Yêu cầu tổng quan

Xây dựng **Single Page Application (SPA)** cho hệ thống dự đoán giá bất động sản TP.HCM. Backend là FastAPI REST API chạy tại `http://localhost:8000`.

**Tech stack:**
- React 18 + TypeScript
- Tailwind CSS
- Recharts (biểu đồ)
- React Query (data fetching + caching)
- React Router v6 (điều hướng)
- Axios (HTTP client)

---

## Cấu trúc trang

```
/              → Dashboard (EDA charts + tổng quan)
/predict       → Form dự đoán giá
/chat          → Chatbot AI
/admin/retrain → Quản lý retrain model
```

---

## Thiết kế chung

- **Màu sắc chủ đạo:** Xanh dương đậm (#1e40af) + trắng + xám nhạt
- **Font:** Inter hoặc hệ thống
- **Layout:** Sidebar trái cố định + content area bên phải
- **Responsive:** Desktop-first, hỗ trợ tablet
- **Dark mode:** Không cần

**Sidebar** (cố định, 240px):
```
Logo + tên app
────────────────
📊 Dashboard
🏠 Dự đoán giá
💬 Chatbot AI
⚙️  Quản lý Model
────────────────
Trạng thái model: [badge]
```

Badge trạng thái model:
- Xanh lá "Sẵn sàng" → khi có model active
- Vàng "Đang retrain..." → khi `status = "running"`
- Đỏ "Chưa có model" → khi chưa retrain lần nào

---

## Trang 1: Dashboard (`/`)

### Header
Tiêu đề "Dashboard Phân tích BĐS TP.HCM" + thời gian cập nhật cuối (lấy từ `GET /retrain/status` → `last_run.triggered_at`).

### Layout: 2 cột trên, 2 cột dưới

**Card 1 — Phân phối giá (Bar Chart)**
- API: `GET /eda/price-distribution`
- Recharts `BarChart` horizontal hoặc vertical
- X-axis: label bin ("0-30", "30-50", ..., "130+"), đơn vị triệu VND/m²
- Y-axis: số lượng căn
- Màu bar: gradient xanh → tím theo độ cao
- Tooltip: "X căn có giá Y–Z triệu/m²"
- Loading skeleton khi fetch

**Card 2 — Feature Importance (Horizontal Bar)**
- API: `GET /feature-importance`
- Recharts `BarChart` layout="vertical"
- Y-axis: tên feature (tiếng Việt)
- X-axis: importance 0–1, hiển thị dạng phần trăm
- Màu bar: xanh dương, độ đậm theo importance
- Sắp xếp từ cao xuống thấp (API đã sort sẵn)
- Tooltip: "Feature X chiếm Y% ảnh hưởng"

**Card 3 — Scatter Plot địa lý (dùng tọa độ lat/lon)**
- API: `GET /eda/scatter/version` → check cache → `GET /eda/scatter/file`
- Parse CSV: cột `tọa độ x` (lat), `tọa độ y` (lon), `diện tích`, `giá/m2`
- Recharts `ScatterChart` với `tọa độ y` (lon) trên X-axis, `tọa độ x` (lat) trên Y-axis
- Màu điểm: gradient theo `giá/m2` (xanh lá = rẻ → đỏ = đắt)
- Tooltip: "Lat: X, Lon: Y | DT: Zm² | Giá: W triệu/m²"
- Cache: lưu `run_id` vào localStorage, chỉ tải lại khi `run_id` thay đổi
- Kích thước điểm nhỏ (r=3), opacity 0.6

**Card 4 — Giá trung vị theo Quận × Loại BĐS (Grouped Bar)**
- API: `GET /eda/district-property-type`
- Recharts `BarChart` grouped
- X-axis: tên quận (rút gọn: "Q.1", "Q.7", "Bình Tân"...)
- Y-axis: giá trung vị (triệu/m²)
- Mỗi group = 1 quận, mỗi bar = 1 loại BĐS (5 màu khác nhau)
- Legend: tên loại BĐS
- Tooltip: "Quận X | Loại Y: Z triệu/m² (N căn)"
- Cho phép filter loại BĐS qua checkbox/dropdown

**Xử lý lỗi:**
- Nếu API trả 404 (chưa có model) → hiển thị empty state:
  ```
  [Icon cảnh báo]
  Chưa có dữ liệu phân tích
  Hệ thống cần được retrain ít nhất 1 lần.
  [Nút "Đi đến Quản lý Model"]
  ```

---

## Trang 2: Dự đoán giá (`/predict`)

### Layout: 2 cột (form trái, kết quả phải)

**Form nhập liệu (cột trái):**

Nhóm 1 — Thông tin cơ bản (bắt buộc):

```
Loại bất động sản *
[Dropdown]
  ├── Căn hộ chung cư  (code: 0)
  ├── Nhà riêng        (code: 2)
  ├── Nhà biệt thự     (code: 3)
  ├── Nhà mặt phố      (code: 4)
  └── Bán đất          (code: 7)

Quận/Huyện *
[Dropdown — 24 quận TP.HCM]

Diện tích (m²) *
[Number input, min=15, max=500, placeholder="80"]
```

Nhóm 2 — Vị trí:

```
Địa chỉ cụ thể (để tự động lấy tọa độ)
[Text input, placeholder="123 Nguyễn Trãi, Quận 5..."]
[Nút "Lấy tọa độ"] → gọi Goong API (nếu tích hợp)
                    hoặc để user nhập thủ công

Hoặc nhập tọa độ thủ công:
Vĩ độ (Latitude)   [Number input, step=0.0001, placeholder="10.73"]
Kinh độ (Longitude)[Number input, step=0.0001, placeholder="106.72"]
```

Nhóm 3 — Thông tin tuỳ chọn (hiển thị/ẩn theo loại BĐS):

```
[Hiển thị nếu loại ≠ Căn hộ]
Mặt tiền (m)  [Number input, min=1, max=30]

[Hiển thị nếu loại ≠ Căn hộ và ≠ Bán đất]
Số tầng       [Number input, min=1, max=20]

[Hiển thị nếu loại ≠ Bán đất]
Số phòng ngủ  [Number input, min=1, max=10]
```

Logic ẩn/hiện theo loại BĐS:
- `loại = 0` (Căn hộ): ẩn Mặt tiền, ẩn Số tầng
- `loại = 7` (Bán đất): ẩn Phòng ngủ, ẩn Số tầng

```
[Nút "Dự đoán giá" — primary, full width]
```

Validation:
- Loại BĐS, Quận, Diện tích, Tọa độ X, Tọa độ Y: bắt buộc
- Diện tích: 15–500
- Highlight đỏ field thiếu khi submit

**Kết quả (cột phải):**

Trạng thái ban đầu: placeholder "Nhập thông tin và nhấn Dự đoán"

Sau khi submit:
- Loading spinner trong nút
- Hiển thị kết quả dạng card lớn:

```
┌─────────────────────────────────┐
│  Kết quả dự đoán                │
│                                 │
│  Giá/m²                         │
│  ╔═══════════════╗              │
│  ║  85.3 triệu   ║              │
│  ╚═══════════════╝              │
│                                 │
│  Tổng giá ước tính              │
│  ┌───────────────┐              │
│  │  6.82 tỷ VND  │              │
│  └───────────────┘              │
│                                 │
│  Thông tin đã nhập:             │
│  • Nhà riêng, Quận 7            │
│  • Diện tích: 80 m²             │
│  • Phòng ngủ: 2                 │
│                                 │
│  ⚠️ Đây là ước tính tham khảo  │
└─────────────────────────────────┘
```

- Nếu `predicted_price_per_m2 = null`: card màu vàng cảnh báo "Model chưa sẵn sàng, hãy chạy retrain"

---

## Trang 3: Chatbot AI (`/chat`)

### Layout: chat UI full height (như messenger)

**Header:**
```
[Avatar bot] Trợ lý BĐS AI    [Nút "Cuộc hội thoại mới"]
```

**Message area (scroll được):**

Tin nhắn Bot (trái):
```
[Avatar] ┌────────────────────────────┐
         │ Chào bạn! Mình sẽ hỏi vài │
         │ thông tin để dự đoán giá.  │
         └────────────────────────────┘
         10:30 AM
```

Tin nhắn User (phải):
```
              ┌────────────────────┐ [Avatar]
              │ nhà riêng 80m2    │
              │ quận 7             │
              └────────────────────┘
                              10:31 AM
```

Tin nhắn kết quả dự đoán (bot, card đặc biệt):
```
[Avatar] ┌────────────────────────────────┐
         │ 🏠 Kết quả dự đoán            │
         │ ─────────────────────────────  │
         │ Giá/m²:    85.3 triệu VND/m²  │
         │ Tổng giá:  ~6.82 tỷ VND       │
         │ ─────────────────────────────  │
         │ Lý do: [giải thích từ AI]      │
         │                                │
         │ [Dự đoán mới] [Điều chỉnh]    │
         └────────────────────────────────┘
```

**Gợi ý nhanh (quick replies) — hiển thị khi chờ nhập:**

Lần đầu (chưa có loại BĐS):
```
[Căn hộ chung cư] [Nhà riêng] [Nhà mặt phố] [Bán đất]
```

Sau khi đủ thông tin bắt buộc:
```
[✓ Dự đoán ngay] [Thêm số phòng ngủ] [Thêm mặt tiền]
```

**Input area (bottom, cố định):**
```
[Textarea — auto-resize, max 3 dòng]  [Nút Gửi →]
```
- Enter: gửi tin nhắn
- Shift+Enter: xuống dòng
- Disable input khi đang chờ phản hồi (hiển thị "..." typing indicator)

**Logic session:**
```javascript
// Mount component
const [sessionId, setSessionId] = useState<string | null>(null)

// Gửi tin nhắn
async function sendMessage(text: string) {
  const res = await api.post('/chat', {
    session_id: sessionId,
    message: text
  })
  setSessionId(res.data.session_id)  // Lưu session từ response
  addMessage('bot', res.data.reply, res.data.is_prediction, res.data.prediction)
}

// Cuộc hội thoại mới
function resetChat() {
  setSessionId(null)
  setMessages([welcomeMessage])
}
```

**Tin nhắn chào mừng ban đầu (không cần gọi API):**
```
"Xin chào! Mình là trợ lý AI chuyên tư vấn giá bất động sản TP.HCM. 
Hãy cho mình biết loại nhà bạn muốn ước tính giá nhé! 🏠"
```

---

## Trang 4: Quản lý Model (`/admin/retrain`)

### Section 1 — Trạng thái & Điều khiển

```
┌─────────────────────────────────────────────┐
│ Trạng thái hệ thống                          │
│                                             │
│  Model hiện tại: [Run #3 — 09/04/2026]      │
│  Trạng thái:     [● Sẵn sàng]               │
│  R² score:       0.891                      │
│  RMSE:           0.243                      │
│                                             │
│  [Nút "Kích hoạt Retrain"]                  │
│  Retrain tự động: mỗi 7 ngày               │
└─────────────────────────────────────────────┘
```

Logic nút Retrain:
- Bình thường: nút primary "Kích hoạt Retrain"
- Đang chạy: nút disabled + spinner "Đang retrain..." + progress text
- Sau khi click: POST `/retrain/trigger` → nếu 200: bắt đầu poll status mỗi 5 giây
- Poll: `GET /retrain/status` → khi `status = "idle"`: dừng poll, reload data

### Section 2 — Xu hướng Metrics (Line Chart)

- API: `GET /retrain/metrics/trend`
- Recharts `LineChart`
- X-axis: date (format "DD/MM/YY")
- Y-axis: giá trị metric
- 3 đường: RMSE (đỏ), MAE (cam), R² (xanh lá)
- Tooltip hiển thị cả 3 giá trị tại cùng điểm thời gian
- Nếu chỉ có 1 điểm: hiển thị dạng scatter thay vì line

### Section 3 — Lịch sử retrain (Table)

- API: `GET /retrain/history?page=X&size=10`
- Columns: ID | Thời gian | Trạng thái | Dòng mới | Thời gian chạy | RMSE | Model thay?

```
| #3 | 09/04/2026 18:30 | ✅ Thành công | +450  | 3m 7s  | 0.243 | ✅ Có |
| #2 | 01/04/2026 10:15 | ✅ Thành công | +1200 | 3m 45s | 0.251 | ✅ Có |
| #1 | 24/03/2026 09:00 | ❌ Thất bại   | —     | 0m 12s | —     | —     |
```

Badge trạng thái:
- `success` → pill xanh lá "✅ Thành công"
- `failed` → pill đỏ "❌ Thất bại"
- `skipped` → pill xám "⏭ Bỏ qua"
- `running` → pill vàng + spinner "🔄 Đang chạy"

Phân trang: Previous / [1] [2] [3] / Next

---

## API Client (axios)

```typescript
// src/api/client.ts
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' }
})

// Intercept 404 → chưa có model active
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 404) {
      // Dispatch event "no-active-model"
    }
    return Promise.reject(err)
  }
)

export default api
```

```typescript
// src/api/endpoints.ts
export const endpoints = {
  predict:           () => api.post('/predict', data),
  retrain: {
    trigger:         () => api.post('/retrain/trigger'),
    status:          () => api.get('/retrain/status'),
    history:         (page, size) => api.get(`/retrain/history?page=${page}&size=${size}`),
    metricsTrend:    () => api.get('/retrain/metrics/trend'),
  },
  eda: {
    priceDistribution:   () => api.get('/eda/price-distribution'),
    districtPropertyType:() => api.get('/eda/district-property-type'),
    scatterVersion:      () => api.get('/eda/scatter/version'),
    scatterFile:         () => api.get('/eda/scatter/file'),
  },
  featureImportance: () => api.get('/feature-importance'),
  chat:              (sessionId, message) =>
                       api.post('/chat', { session_id: sessionId, message }),
}
```

---

## Enum constants

```typescript
// src/constants/enums.ts
export const REAL_ESTATE_TYPES = [
  { code: 0, label: 'Căn hộ chung cư' },
  { code: 2, label: 'Nhà riêng' },
  { code: 3, label: 'Nhà biệt thự, liền kề' },
  { code: 4, label: 'Nhà mặt phố' },
  { code: 7, label: 'Bán đất' },
]

export const DISTRICTS = [
  { code: 0,  label: 'Bình Chánh' },
  { code: 1,  label: 'Bình Tân' },
  { code: 2,  label: 'Bình Thạnh' },
  { code: 3,  label: 'Cần Giờ' },
  { code: 4,  label: 'Củ Chi' },
  { code: 5,  label: 'Gò Vấp' },
  { code: 6,  label: 'Hóc Môn' },
  { code: 7,  label: 'Nhà Bè' },
  { code: 8,  label: 'Phú Nhuận' },
  { code: 9,  label: 'Quận 1' },
  { code: 10, label: 'Quận 10' },
  { code: 11, label: 'Quận 11' },
  { code: 12, label: 'Quận 12' },
  { code: 13, label: 'Quận 2' },
  { code: 14, label: 'Quận 3' },
  { code: 15, label: 'Quận 4' },
  { code: 16, label: 'Quận 5' },
  { code: 17, label: 'Quận 6' },
  { code: 18, label: 'Quận 7' },
  { code: 19, label: 'Quận 8' },
  { code: 20, label: 'Quận 9' },
  { code: 21, label: 'Thủ Đức' },
  { code: 22, label: 'Tân Bình' },
  { code: 23, label: 'Tân Phú' },
]

// Fields ẩn theo loại BĐS
export const HIDDEN_FIELDS: Record<number, string[]> = {
  0: ['mat_tien', 'so_tang'],          // Căn hộ
  7: ['phong_ngu', 'so_tang'],         // Bán đất
}
```

---

## Các component cần tạo

```
src/
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   └── AppLayout.tsx
│   ├── charts/
│   │   ├── PriceDistributionChart.tsx
│   │   ├── FeatureImportanceChart.tsx
│   │   ├── ScatterPlotChart.tsx
│   │   ├── DistrictHeatmap.tsx
│   │   └── MetricsTrendChart.tsx
│   ├── predict/
│   │   ├── PredictForm.tsx
│   │   └── PredictResult.tsx
│   ├── chat/
│   │   ├── ChatWindow.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── PredictionCard.tsx
│   │   └── QuickReplies.tsx
│   ├── retrain/
│   │   ├── StatusCard.tsx
│   │   ├── HistoryTable.tsx
│   │   └── RetrainButton.tsx
│   └── common/
│       ├── EmptyState.tsx       (404 no-model state)
│       ├── LoadingSkeleton.tsx
│       └── ModelStatusBadge.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── PredictPage.tsx
│   ├── ChatPage.tsx
│   └── RetrainPage.tsx
├── api/
│   ├── client.ts
│   └── endpoints.ts
├── hooks/
│   ├── useRetainStatus.ts    (poll mỗi 5s khi running)
│   └── useScatterCache.ts    (localStorage cache)
└── constants/
    └── enums.ts
```

---

## Lưu ý triển khai

1. **CORS:** Backend FastAPI cần thêm `CORSMiddleware` cho origin của frontend
2. **Scatter file lớn:** Parse CSV bằng `papaparse` thay vì tự parse
3. **Retrain polling:** Dùng `setInterval` + cleanup trong `useEffect` để tránh memory leak
4. **Session chat:** Lưu `session_id` trong `useState`, không cần localStorage (reset khi reload là hợp lý)
5. **Empty state toàn cục:** Nếu `/retrain/status` → `last_run = null`, hiển thị banner cảnh báo ở tất cả trang EDA

```typescript
// Thêm vào main.py của FastAPI:
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)
```
