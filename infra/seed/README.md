# CineSense Data Recovery Guide

Chào bạn! Đây là hướng dẫn để khôi phục dữ liệu phim và các vector tìm kiếm sau khi bạn đã pull dự án này về.

## 1. Khởi động Infrastructure
Đầu tiên, hãy khởi động các container Docker:
```bash
docker-compose up -d
```

**Lưu ý:** PostgreSQL sẽ tự động khôi phục dữ liệu từ `infra/seed/postgres/init_data.sql` khi container được tạo lần đầu tiên.

## 2. Khôi phục Qdrant (Vector Database)
Vì Qdrant không tự động nhận snapshot, bạn cần chạy script khôi phục sau khi các container đã chạy:

```bash
# Đảm bảo bạn đã activate venv và cài đủ requirements
python scripts/restore_data.py
```

## 3. Kiểm tra dữ liệu
Bạn có thể chạy thử server API để kiểm tra:
```bash
python -m api.main
```

Hoặc truy cập GUI của Qdrant tại: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---
**Dành cho người duy trì (Maintainer):**
Để cập nhật dữ liệu mẫu (sau khi đã crawl thêm phim mới):
```bash
python scripts/backup_data.py
```
Sau đó commit các file trong `infra/seed/` lên GitHub.
