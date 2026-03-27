# Hệ Thống Tìm Kiếm Phim Đa Năng (Multi-Field Movie Search)

Xây dựng một Search Engine thống nhất, xử lý hiệu quả tất cả 3 loại truy vấn:
- **Tên riêng** (VD: *"Inception"*, *"Spider Man"*)
- **Nội dung / Thể loại** (VD: *"phim hành động có người nhện"*)
- **Ngữ cảnh** (VD: *"phim hack não về giấc mơ"*)

## Kiến Trúc 3 Giai Đoạn

```
Query Input
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  STAGE 1: MULTI-FIELD RECALL (Lấy ~50 ứng viên)         │
│                                                          │
│  ┌────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ BM25/Fuzzy │  │  Genre Keyword  │  │    SBERT     │  │
│  │ Title Match│  │  Exact Match    │  │ Dense Vector │  │
│  │  (Tên phim)│  │  (Thể loại)     │  │  (Ngữ cảnh)  │  │
│  └─────┬──────┘  └────────┬────────┘  └──────┬───────┘  │
│        └────────────┬─────┘                  │          │
│                     └──────────┬─────────────┘          │
│                                ▼                         │
│              Weighted Score Sum + Union Top 50           │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  STAGE 2: SMART RE-RANKING (Xếp hạng lại)               │
│                                                          │
│  Final Score = (Title * W1) + (Genre * W2) + (SBERT * W3│
│                                                          │
│  ┌───────────────────────────────┐                       │
│  │  Tự động điều chỉnh Trọng số │                       │
│  │  Query ngắn (≤3 từ): W1=1.0  │                       │
│  │  Query dài (>3 từ):  W3=0.9  │                       │
│  └───────────────────────────────┘                       │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│  STAGE 3: ABSA REFINEMENT (Lọc tinh theo cảm xúc)        │
│                                                          │
│  Nếu query chứa tính từ cảm xúc:                        │
│  "phim hay" → ABSA Overall: Positive ↑ điểm thưởng      │
│  "phim khó đoán" → ABSA Script: Positive ↑ điểm thưởng  │
│  "kỹ xảo đẹp" → ABSA Visuals: Positive ↑ điểm thưởng   │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
               Top 5-10 Kết quả Cuối cùng
```

## Phương Pháp Xử Lý Từng Vùng

### Vùng 1: Tên phim (BM25 + Fuzzy Match)

| Kỹ thuật | Ưu điểm | Nhược điểm |
|----------|---------|------------|
| `BM25` | Bắt đúng từ khóa quan trọng, xử lý tên dài tốt | Cần cài `rank_bm25` |
| `Fuzzy (thefuzz)` | Chịu được lỗi chính tả, gõ sai vẫn ra | Chậm hơn BM25 với dataset lớn |

> **Khuyến nghị:** Dùng `BM25` làm chính, `Fuzzy` làm backup khi BM25 không ra kết quả nào > 50 điểm.

### Vùng 2: Thể loại (Keyword Exact/Partial Match)

Đơn giản nhất, hiệu quả nhất: kiểm tra xem các từ trong query có xuất hiện trong cột `genres` không.

```
query = "action horror" 
→ Phim có genre "Action" ✓ +80 điểm
→ Phim có genre "Horror" ✓ +80 điểm
→ Phim có cả hai +160 điểm (cực kỳ phù hợp)
```

### Vùng 3: Ngữ cảnh (SBERT Semantic Retrieval)

SBERT (`sentence-transformers/all-MiniLM-L6-v2`) sẽ encode cả câu query thành **Dense Vector** và so sánh với toàn bộ `review_profile` đã được vector hóa sẵn:

```
query = "phim về giấc mơ và vòng lặp thời gian"
→ SBERT hiểu = tìm phim có vector ngữ nghĩa gần nhất
→ Trả về: Inception (0.91), Paprika (0.88), Edge of Tomorrow (0.82)
```

> [!IMPORTANT]
> Cần **pre-compute và cache** toàn bộ SBERT vectors cho 4910 phim vào file `.npy` để tránh tính lại mỗi lần search (tốn ~5 min lần đầu, sau đó load < 1s).

### Giai Đoạn 2: Điều chỉnh Trọng số Thông minh

| Loại Query | W1 (Title) | W2 (Genre) | W3 (SBERT) |
|-----------|------------|------------|------------|
| Ngắn ≤ 3 từ | 1.0 | 0.8 | 0.3 |
| Trung bình 4-6 từ | 0.7 | 0.8 | 0.6 |
| Dài > 6 từ | 0.2 | 0.8 | 1.0 |

### Giai Đoạn 3: ABSA Refinement (Bonus Scoring)

Bảng ánh xạ từ câu truy vấn sang ABSA Aspect:

| Từ trong query | ABSA Aspect | Sentiment |
|---------------|-------------|-----------|
| "hay", "xuất sắc", "good" | overall | positive |
| "kịch bản hay", "plot twist" | script | positive |
| "kỹ xảo đẹp", "CGI", "visual" | visuals | positive |
| "diễn xuất tốt", "acting" | acting | positive |
| "cuốn", "pace", "nhịp độ" | pacing | positive |
| "nhạc hay", "soundtrack" | music | positive |

**Điểm thưởng ABSA:**
```
absa_bonus = Σ(absa_score[aspect][positive] * 20)
final_score = stage2_score + absa_bonus
```

## Proposed Changes

### Search Engine Module

#### [NEW] `search_engine.py` (trong thư mục dự án)
- Hàm `build_sbert_index(df)`: Pre-compute SBERT vectors, save `.npy`
- Hàm `bm25_title_score(query, df)`: Tính điểm BM25 cho tên phim
- Hàm `genre_score(query, df)`: Tính điểm khớp thể loại
- Hàm `sbert_context_score(query, sbert_index)`: Tính điểm ngữ cảnh
- Hàm `absa_bonus_score(query, absa_profiles)`: Tính điểm thưởng từ ABSA
- Hàm `smart_search(query, ...)`: Hàm tổng hợp gọi tất cả các bước trên

#### [MODIFY] [06_Demo_UseCases.ipynb](file:///d:/NguyenHoangHa_nam3/HK2_D1/NLP/project/Notebook_Report/Notebook_Report/06_Demo_UseCases.ipynb) 
- Tích hợp `search_engine.py` để demo tính năng tìm kiếm thông minh
- Thêm các ví dụ demo cho cả 3 loại truy vấn

## Verification Plan

### Automated Tests
Chạy 3 loại test case để kiểm tra hệ thống:
```python
# Test 1: Tên phim chính xác
assert search("Inception")[0]['title'] == "Inception"

# Test 2: Thể loại
assert all("Horror" in r['genres'] for r in search("horror movie")[:3])

# Test 3: Ngữ cảnh
results = search("phim về giấc mơ và vòng lặp thời gian")
assert "Inception" in [r['title'] for r in results[:5]]
```

### Manual Verification
Demo trực tiếp trên Notebook 06 với ít nhất 5 câu query khác nhau thể hiện đầy đủ 3 trường hợp.
