## Tiền xử lý dữ liệu (1.5 điểm)

### 1. Làm sạch dữ liệu (0.5)
Trong notebook `02_Data_Preprocessing_EDA.ipynb`, dữ liệu văn bản (đặc biệt là `overview` và `content` của review) được làm sạch theo các bước chính để chuẩn hoá đầu vào trước khi build profile và đưa vào vectorization:

- **Lowercase**: chuyển toàn bộ chữ về dạng chữ thường để giảm nhiễu do khác biệt hoa/thường.
- **Remove URL**: xoá các chuỗi URL (`http(s)://...` và `www....`) để tránh vector bị ảnh hưởng bởi các token không mang nội dung cảm xúc/ngữ nghĩa.
- **Remove HTML tags**: dùng `BeautifulSoup` để bóc tách phần text thực, loại bỏ các thẻ HTML (tránh việc token hoá nhầm tag/markup).
- **Remove punctuation & ký tự không mong muốn**: dùng regex để xoá dấu câu/ký tự đặc biệt, giữ lại chữ cái/số và khoảng trắng (giúp mô hình TF‑IDF/Word frequency ổn định hơn).
- **Xử lý emoji/ký tự đặc biệt**: thay các chuỗi emoji/pictograph bằng khoảng trắng để hạn chế token “rác”.
- **Chuẩn hoá khoảng trắng**: gộp nhiều khoảng trắng về 1, trim đầu/cuối để giảm biến thiên không cần thiết.

Nhờ vậy, review text sau tiền xử lý có dạng nhất quán, giảm nhiễu trước các bước thống kê và mô hình hoá.

### 2. Xử lý ngôn ngữ (0.5)
Sau khi làm sạch, notebook thực hiện các thao tác xử lý ngôn ngữ ở mức chuẩn bị dữ liệu:

- **Tokenization (tách từ)**: dùng tách theo khoảng trắng (`.split()`) trên text đã được làm sạch để tạo chuỗi token phục vụ thống kê độ dài và/hoặc vector hóa.
- **Word frequency / n-gram thống kê**: ở phần EDA bổ sung, notebook dùng `CountVectorizer` (stopword removal theo `english`) để rút ra **top từ xuất hiện nhiều nhất** trên `review_profile` (sampling nhằm chạy nhanh).
- **Stopword removal**: stopword tiếng Anh được loại bỏ trong thống kê word frequency để tập trung vào các từ mang nội dung.
- **Stemming/word segmentation**: hiện notebook tập trung vào bước làm sạch + tokenization + thống kê tần suất; stemming/word segmentation có thể không được áp dụng trực tiếp trong `02`. (Nếu cần khớp 100% yêu cầu “stemming/segmentation”, bạn có thể bổ sung như bước mở rộng hoặc ghi rõ ở phần future work.)

Ghi chú theo đúng barem: phần xử lý ngôn ngữ ở đây thể hiện bằng cơ chế **tokenization + loại stopwords + thống kê n-gram/từ** trước khi qua notebook 3.

### 3. Trực quan dữ liệu (0.5)
Notebook `02_Data_Preprocessing_EDA.ipynb` vẽ các biểu đồ EDA nhằm hiểu sâu phân bố dữ liệu văn bản trước khi huấn luyện/bắt đầu retrieval:

**(a) Độ dài văn bản**
- **Distribution độ dài `movie_profile` (tokens)**: biểu đồ histogram cho biết độ dài profile phim sau khi ghép `title + overview + genres + review snippets`. Điều này giúp đánh giá độ dài đầu vào cho TF‑IDF/embedding và mức độ “dày” thông tin theo từng phim.
- **Distribution độ dài `review_profile` (tokens)**: biểu đồ histogram cho biết độ dài phần review text (chỉ review) dùng cho đúng mục tiêu đề tài: *gợi ý dựa trên review text*.

**(b) Số lượng dữ liệu theo phim**
- **Số lượng review / phim**: biểu đồ cho biết mỗi phim trung bình có bao nhiêu review (proxy mức độ phong phú của dữ liệu text).

**(c) Phân bố theo thuộc tính (proxy cho phân bố lớp)**
- **Top Genres (số lượng movies)**: biểu đồ barplot top genre theo số lượng phim. Trong bài toán recommendation dựa trên nội dung, genre được dùng như **proxy cho phân bố nhóm nội dung** (vì notebook không có nhãn lớp sentiment/aspect trực tiếp ở giai đoạn này).

**(d) Word frequency**
- **Top Word Frequency (trên review text)**: biểu đồ barplot các từ xuất hiện nhiều nhất trên `review_profile` (sau stopword removal). Biểu đồ này giúp hiểu:
  - Các từ mang tính mô tả chung (ví dụ “film”, “movie”, “story”, “good/like…”) chiếm ưu thế ra sao,
  - Có tồn tại các từ đặc trưng theo cụm ngữ nghĩa mà retrieval có thể khai thác tốt.

**(e) Distribution rating (nếu có)**
- **Distribution Review Rating**: biểu đồ histogram thể hiện phân bố rating theo review (`rating`), hữu ích để hiểu mức độ thiên lệch (bias) của tập dữ liệu.

Tóm lại, các biểu đồ ở notebook 02 cung cấp đầy đủ 3 ý chính theo barem: (1) độ dài dữ liệu, (2) phân bố theo nhóm (genre), (3) từ vựng/word frequency (và rating nếu có), từ đó hỗ trợ giải thích và thiết kế bước mô hình hoá ở notebook 3.

