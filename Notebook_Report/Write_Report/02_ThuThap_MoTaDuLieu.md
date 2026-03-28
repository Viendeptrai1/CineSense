# Chương 2. Thu thập và mô tả dữ liệu

## 2.1. Nguồn dữ liệu
- Nguồn chính: TMDB API (metadata phim + review).
- Dữ liệu nội bộ sau ETL lưu trong các bảng core:
  - `core_movies`
  - `core_reviews`
  - `core_genres`
  - `core_movie_genres`

## 2.2. Quy trình cào dữ liệu
1. Gọi API theo từng trang phim.
2. Lấy metadata phim (title, overview, release date, genres, poster).
3. Lấy review theo từng phim.
4. Chuẩn hóa và nạp vào schema core.

## 2.3. Các trường dữ liệu quan trọng cho NLP
### Bảng phim (`core_movies`)
- `id`, `tmdb_id`, `title`, `overview`, `release_date`, `poster_path`

### Bảng review (`core_reviews`)
- `movie_id`, `content`, `source`, `language`, `rating`

### Bảng genre liên kết
- ánh xạ nhiều-nhiều giữa phim và thể loại.

## 2.4. Mô tả dữ liệu thô
- Dữ liệu ban đầu gồm cả metadata và review với độ dài không đồng đều.
- Có nhiễu thường gặp:
  - review rỗng/ngắn quá mức
  - URL, ký tự đặc biệt, HTML
  - ngôn ngữ lẫn lộn nếu không lọc

## 2.5. Chính sách ngôn ngữ và chất lượng dữ liệu
- Dự án ưu tiên **English-first** cho train/eval retrieval.
- Bản ghi thiếu thông tin quan trọng (ví dụ overview rỗng) được loại hoặc xử lý theo tiêu chí nhất quán.
- Mục tiêu: giảm nhiễu để mô hình tập trung vào tín hiệu ngữ nghĩa.

## 2.6. Tập dữ liệu xuất ra cho notebook
- `Notebook_Report/cinesense_movies.csv`
- `Notebook_Report/cinesense_reviews.csv`
- Tập sau xử lý:
  - `Notebook_Report/cleaned_profiles.csv`
  - `Notebook_Report/absa_clean_reviews.csv`

## 2.7. Liên kết đến notebook minh chứng
- Thu thập dữ liệu: `01_Data_Collection.ipynb`
- Mô tả và thống kê ban đầu: `02_Data_Preprocessing_EDA.ipynb`
