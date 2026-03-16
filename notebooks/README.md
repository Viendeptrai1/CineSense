# Notebooks

## `kaggle_absa_train.ipynb`

Notebook để **train model ABSA trên Kaggle** (dùng GPU P100/T4/H100 cho nhanh).

### Cách dùng

1. **Chuẩn bị dữ liệu**
   - File labeled JSONL: `training/data/absa/labeled_absa_auto.jsonl` (hoặc `labeled_absa.jsonl`).

2. **Trên Kaggle**
   - Tạo **Dataset** mới, upload file JSONL (có thể zip nếu lớn).
   - Tạo **Notebook** mới, chọn **Settings → Accelerator → GPU**.
   - **Add data**: thêm dataset vừa tạo.

3. **Trong notebook**
   - Copy nội dung `kaggle_absa_train.ipynb` vào notebook Kaggle (hoặc upload file .ipynb).
   - Nếu đường dẫn data khác, sửa `INPUT_DATA_PATH` (hoặc để notebook tự tìm file `.jsonl` trong `/kaggle/input`).
   - **Run All**.

4. **Lấy kết quả**
   - Artifact nằm ở `/kaggle/working/absa_artifact` (config.json, tokenizer, head.pt, schema.json, ...).
   - Vào **Output** tab → tải về hoặc tạo Dataset từ Output, rồi copy vào `training/artifacts/absa_latest` trong repo để API dùng.

### Lưu ý

- Kaggle có sẵn `torch`, `transformers`; không cần cài thêm.
- Batch size mặc định 16; GPU H100 có thể tăng 32–64 để train nhanh hơn.
