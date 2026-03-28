# Phụ lục. Ánh xạ barem -> nội dung báo cáo -> minh chứng

## A. Mức độ hoàn thiện đề tài (1.5 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Xác định đúng bài toán NLP | Chương 1, mục 1.3 | `00_Outline.md`, `01_GioiThieu_BaiToan.md` |
| Phân tích yêu cầu (input-output-phạm vi) | Chương 1, mục 1.4-1.6 | `01_GioiThieu_BaiToan.md` |
| Thu thập & mô tả dữ liệu | Chương 2 | `01_Data_Collection.ipynb`, `02_ThuThap_MoTaDuLieu.md` |

## B. Cơ sở lý thuyết (1.0 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Kiến thức NLP cơ bản | Chương 1, Chương 3 | `01_GioiThieu_BaiToan.md`, `03_TienXuLy_EDA.md` |
| Thuật toán/mô hình chính | Chương 4 | `03_Modeling_Baselines.ipynb`, `04_Advanced_ABSA_Modeling.ipynb`, `04_XayDungMoHinh.md` |

## C. Tiền xử lý dữ liệu (1.5 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Làm sạch dữ liệu | Chương 3, mục 3.2 | `02_Data_Preprocessing_EDA.ipynb` |
| Xử lý ngôn ngữ | Chương 3, mục 3.3-3.4 | `02_Data_Preprocessing_EDA.ipynb`, `03_Modeling_Baselines.ipynb` |
| Trực quan dữ liệu | Chương 3, mục 3.5 | `02_Data_Preprocessing_EDA.ipynb` |

## D. Xây dựng mô hình (2.5 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Lựa chọn mô hình phù hợp | Chương 4, mục 4.2-4.3 | `03_Modeling_Baselines.ipynb`, `04_Advanced_ABSA_Modeling.ipynb` |
| Huấn luyện mô hình | Chương 4, mục 4.5 | `03_Modeling_Baselines.ipynb`, `04_Advanced_ABSA_Modeling.ipynb` |
| Pipeline hoàn chỉnh | Chương 4, mục 4.4 | `06_Demo_UseCases.ipynb`, API runtime logs |
| Tối ưu/so sánh | Chương 4, mục 4.6 | `05_Model_Evaluation.ipynb` |

## E. Đánh giá & thực nghiệm (1.5 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Chỉ số đánh giá định lượng | Chương 5, mục 5.2 | `05_Model_Evaluation.ipynb`, `eval_results.json` |
| Minh họa trực quan | Chương 5, mục 5.5 | Biểu đồ/bảng trong `05_Model_Evaluation.ipynb` |
| Thảo luận kết quả | Chương 5, mục 5.6-5.7 | `05_DanhGia_ThucNghiem.md` |

## F. Ứng dụng demo (1.0 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Demo chạy được | Chương 6 | `06_Demo_UseCases.ipynb`, API + frontend |
| Input/Output/UI rõ ràng | Chương 6, mục 6.3 | `frontend/` + log endpoint |
| Kịch bản sử dụng cụ thể | Chương 6, mục 6.2 | `06_Demo_NLP.md` |

## G. Báo cáo & bảo vệ (1.0 điểm)
| Tiêu chí barem | Vị trí trong báo cáo | Minh chứng notebook/tệp |
| --- | --- | --- |
| Báo cáo đúng chuẩn | Toàn bộ chương 1-7 + phụ lục | Bộ file trong `Write_Report/` |
| Trả lời câu hỏi chuyên môn | Chương 4-5 + phụ lục | Bảng so sánh, metric, phân tích lỗi |

## Ghi chú vận hành khi chốt báo cáo
- Mỗi bảng kết quả cần trích dẫn notebook/tệp số liệu nguồn.
- Hình minh họa nên đặt tên theo chương để tránh nhầm khi nộp.
- Khi có thay đổi kết quả thực nghiệm, cập nhật lại map này trước khi xuất bản PDF cuối.
