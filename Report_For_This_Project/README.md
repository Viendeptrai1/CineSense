# Report_For_This_Project

Thư mục này là dự án LaTeX dùng để viết báo cáo đồ án NLP cho `CineSense`.

## Mục tiêu

- Bám sát barem chấm điểm trong `Barem_DoAn_NLP.pdf`
- Theo dõi tiến độ viết báo cáo, thí nghiệm, hình/bảng và evidence
- Có thể build cục bộ bằng `XeLaTeX`

## Cấu trúc chính

- `main.tex`: file gốc để biên dịch
- `chapters/`: nội dung từng chương
- `styles/`: gói style, format, macro
- `metadata/`: thông tin tiêu đề, từ viết tắt
- `bib/`: tài liệu tham khảo
- `planning/`: checklist barem, evidence tracker, next tasks
- `figures/`, `tables/`: nơi lưu hình và bảng

## Build cục bộ

### Cách 1: Dùng Makefile

```bash
cd Report_For_This_Project
make pdf
```

### Cách 2: Dùng XeLaTeX thủ công

```bash
cd Report_For_This_Project
xelatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

## Lưu ý

- Máy hiện có `xelatex`, nhưng chưa có `latexmk`
- Máy hiện chưa có `IEEEtran.bst`, nên project đang dùng `unsrtnat` để build ổn định trong giai đoạn viết nháp; khi cài đủ bộ TeX có thể đổi lại style IEEE trong `main.tex`
- File `latexmkrc` vẫn được tạo sẵn để dùng sau khi cài `latexmk`
- Chưa được để sót bất kỳ `TODO` nào trong bản nộp cuối
- Mọi hình/bảng cần được dẫn chiếu trong nội dung
