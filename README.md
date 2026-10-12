# PDF to BlueBook

Ứng dụng Streamlit chạy local trên Windows để chuyển PDF SAT Verbal có text layer thành một bài luyện tập HTML dùng offline.

## Chức năng MVP

- Trích xuất text, ảnh nhúng và bảng có cấu trúc từ PDF bằng PyMuPDF.
- Gọi Gemini 2.5 Flash để parse câu hỏi ABCD, passage và answer key thành dữ liệu có cấu trúc.
- Review và sửa passage, câu hỏi, bốn lựa chọn, đáp án và ảnh trước khi export.
- Xuất một HTML tự đủ có timer, điều hướng, đánh dấu câu, highlight passage, trạng thái đã làm và chấm điểm.
- Hiển thị/tải báo cáo lỗi JSON. Nếu PDF không có answer key, chọn dừng hoặc xuất bài không chấm điểm.

## Cài và chạy

Mở PowerShell tại thư mục dự án rồi chạy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

Tạo Gemini API key trong Google AI Studio, dán key vào thanh bên, chọn PDF có text layer rồi bấm **Phân tích PDF**. API key không được lưu vào file hoặc session state.

## Giới hạn MVP

- Không xử lý PDF scan không có text layer.
- Image được tự gán khi trang đó chỉ có một ảnh; nếu có nhiều ảnh, chọn lại ảnh trong màn hình review.
- Highlight và đánh dấu câu trong HTML chỉ tồn tại khi tab trình duyệt đang mở.
- Bảng chỉ tự gán khi Gemini nhận diện đúng quan hệ; có thể chọn lại bảng trong màn hình review.
