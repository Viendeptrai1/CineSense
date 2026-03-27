# training/ (legacy utilities)

Thư mục này hiện giữ các script/utility phục vụ nghiên cứu cục bộ.

## Quy ước dự án hiện tại

- **Không dùng `training/` làm luồng train chính thức cho artifact runtime.**
- Luồng chính thức để train model là qua notebook trong `Notebook_Report/`.
- Artifact dùng cho API/web phải nằm dưới:
  - `Notebook_Report/training/artifacts/...`
  - `Notebook_Report/absa/artifacts/...`

## Khi nào dùng thư mục này?

- Thử nghiệm nhanh, benchmark nội bộ, hoặc tái sử dụng code helper.
- Nếu có kết quả tốt, cần port lại quy trình vào notebook tương ứng trong `Notebook_Report/`.
