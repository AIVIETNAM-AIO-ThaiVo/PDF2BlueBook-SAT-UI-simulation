# 📘 PDF to BlueBook

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Gemini](https://img.shields.io/badge/AI-Gemini-8E75B2?logo=google&logoColor=white)](https://ai.google.dev/)

> *Một self-app cá nhân giúp giáo viên biến đề SAT dạng PDF thành bài luyện tập kiểu BlueBook để sử dụng nhanh trong giờ dạy học.*

## ✨ Tính năng chính

- 📄 Đọc PDF SAT Reading & Writing và chuyển thành passage, câu hỏi, lựa chọn, đáp án và hình ảnh.
- 🤖 Dùng Gemini để phân tích câu hỏi, sửa lỗi chính tả/spacing phổ biến và nhận diện graph/table bằng vùng ảnh.
- 🧹 Giữ lại định dạng quan trọng như **in đậm**, *in nghiêng*, gạch chân, bullet và chỗ trống đáp án.
- 🛠️ Có màn hình review để kiểm tra và chỉnh dữ liệu trước khi xuất đề.
- 🌐 Xuất HTML offline với giao diện hiện đại, timer, cuộn passage và điều hướng câu hỏi.
- 🖍️ Highlight hai chiều: quét đoạn thường để highlight, quét đoạn đã highlight để bỏ highlight.
- 🚩 Đánh dấu câu cần xem lại, theo dõi câu đã làm/chưa làm và lọc danh sách câu hỏi.
- 📊 Sau khi nộp bài, xem từng câu bằng các ô màu xanh/đỏ và mở chi tiết đáp án khi cần.

## 🧭 Tổng quan

PDF to BlueBook được xây dựng cho một nhu cầu rất cụ thể trong quá trình dạy học: giảm thời gian xử lý thủ công những đề PDF có layout phức tạp, bảng, hình, gạch chân và chỗ trống. Đây là công cụ cá nhân chạy trên Windows, ưu tiên **work được trước**, dữ liệu ở trong phiên làm việc và file HTML sau khi xuất có thể mở offline trên trình duyệt.

Quy trình sử dụng:

1. 📥 Tải đề SAT PDF lên ứng dụng Streamlit.
2. 🔎 PyMuPDF đọc nội dung; Gemini phân tích câu hỏi và nhận diện hình/bảng cần tách.
3. ✍️ Kiểm tra, sửa và bổ sung dữ liệu trong màn hình review.
4. ⏱️ Chọn thời lượng rồi xuất bài luyện tập HTML.
5. 🧑‍🏫 Mở HTML trên trình duyệt và sử dụng trực tiếp trong giờ học.

### 👤 Tác giả

Được xây dựng và duy trì như một self-app cá nhân để chuẩn bị bài và hỗ trợ dạy học.

## 🚀 Cách sử dụng

Khởi động ứng dụng bằng PowerShell:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Nhập Gemini API key trong ứng dụng, tải PDF, kiểm tra dữ liệu đã parse, chọn thời lượng và bấm **Render HTML offline**. Sau đó mở file HTML được tạo bằng trình duyệt.

Bài HTML hỗ trợ:

- cuộn passage và bật/tắt chế độ highlight;
- đánh dấu câu cần xem lại;
- chuyển nhanh giữa các câu và lọc câu đã làm/chưa làm;
- timer được đặt trước lúc render;
- nộp bài và xem kết quả theo từng câu;
- chế độ không có đáp án khi đề nguồn không cung cấp answer key.

## 📦 Cài đặt

Hiện tại dự án hỗ trợ Windows, Python 3.10 trở lên và cần Gemini API key để parse câu hỏi.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Các thành phần chính gồm Streamlit, PyMuPDF, Pillow và Google GenAI SDK. API key chỉ được dùng trong phiên hiện tại và không được ghi vào source code.

## 💬 Phản hồi và đóng góp

Nếu gặp lỗi trích xuất, hãy ghi lại mẫu PDF, kết quả ứng dụng tạo ra và kết quả mong muốn rồi mở issue hoặc change request. Các đóng góp giúp tăng độ chính xác khi đọc PDF, nhận diện graph/table, cải thiện màn hình review và trải nghiệm sử dụng trong lớp học đều được hoan nghênh.

## ⚠️ Giới hạn hiện tại

- PDF scan không có text layer có thể chưa được hỗ trợ ổn định.
- Gemini hiện cần thiết cho việc parse câu hỏi và nhận diện graph/table.
- Chất lượng trích xuất phụ thuộc vào layout và text layer của PDF; nên review trước khi dùng trong lớp.
- Highlight và trạng thái đánh dấu chỉ tồn tại trong phiên trình duyệt đang mở, không ghi ngược vào PDF nguồn.
