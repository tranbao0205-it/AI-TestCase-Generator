# AI Test Case Generator

AI Test Case Generator là một hệ thống hỗ trợ sinh Test Case tự động cho các ứng dụng Web từ mô tả nghiệp vụ, tài liệu đặc tả hoặc giao diện người dùng. Mục tiêu của dự án là giảm thời gian xây dựng bộ Test Case, đồng thời đảm bảo các trường hợp kiểm thử được tạo ra có tính nhất quán và bám sát nghiệp vụ.

Khác với cách chỉ gửi một prompt trực tiếp đến mô hình AI, hệ thống xây dựng thêm tầng Rule Engine và Workflow xử lý nhiều bước để chuẩn hóa dữ liệu đầu vào, xác định chức năng cần kiểm thử, tổ chức Test Case theo nhóm và kiểm tra độ bao phủ trước khi xuất kết quả.

Người dùng có thể xem trước, chỉnh sửa, sinh lại Test Case và xuất toàn bộ kết quả ra file Excel phục vụ quá trình kiểm thử.

---

## Chức năng chính

- Sinh Test Case từ mô tả nghiệp vụ.
- Sinh Test Case từ tài liệu đặc tả (TXT, DOCX, PDF, Markdown).
- Sinh Test Case từ hình ảnh giao diện.
- Phân nhóm Test Case theo chức năng.
- Chỉnh sửa trực tiếp trước khi xuất.
- Sinh lại một Test Case hoặc toàn bộ chức năng.
- Xuất kết quả ra file Excel nhiều Sheet.
- Lưu lịch sử làm việc và quản lý các file đã tạo.

---

## Kiến trúc hệ thống

Hệ thống được chia thành các thành phần độc lập để thuận tiện cho việc mở rộng và bảo trì.

```
Người dùng
      │
      ▼
Frontend
      │
      ▼
Flask API
      │
      ▼
Workflow Service
      │
 ┌────┴────┐
 ▼         ▼
Rule      File
Engine    Reader
      │
      ▼
AI Service
      │
      ▼
Normalize dữ liệu
      │
      ▼
Preview Test Case
      │
      ▼
Excel Service
```

---

## Quy trình xử lý

1. Người dùng nhập mô tả hoặc tải tài liệu/giao diện.
2. Hệ thống phân tích yêu cầu và xác định chức năng cần kiểm thử.
3. Rule Engine bổ sung các quy tắc nghiệp vụ tương ứng.
4. AI sinh Test Case theo từng chức năng.
5. Kết quả được chuẩn hóa và gom nhóm.
6. Người dùng xem trước và chỉnh sửa nếu cần.
7. Có thể sinh lại một Test Case hoặc toàn bộ chức năng.
8. Xuất kết quả thành file Excel.

---

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|------------|-----------|
| Backend | Flask |
| Frontend | HTML, CSS, JavaScript |
| AI | OpenAI API |
| Database | SQLite |
| Excel | openpyxl |
| File Reader | pdfplumber, python-docx, Markdown |
| Ngôn ngữ | Python 3.10+ |

---

## Cấu trúc thư mục

```text
project/
│
├── app.py
├── services/
│   ├── ai_service.py
│   ├── workflow_service.py
│   ├── rule_engine.py
│   ├── scenario_rule_engine.py
│   ├── excel_service.py
│   ├── history_service.py
│   └── file_reader.py
│
├── database/
├── static/
├── templates/
├── uploads/
└── outputs/
```

---

## Cài đặt

### Tạo môi trường

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux/macOS

```bash
source venv/bin/activate
```

### Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### Cấu hình

Tạo file `.env`

```env
OPENAI_API_KEY=YOUR_API_KEY
OPENAI_MODEL=YOUR_MODEL
SECRET_KEY=YOUR_SECRET_KEY
```

### Khởi động

```bash
python app.py
```

---

## Hướng dẫn sử dụng

### Sinh Test Case từ mô tả

Nhập yêu cầu nghiệp vụ vào khung chat, hệ thống sẽ tự động phân tích và sinh Test Case theo từng chức năng.

### Sinh Test Case từ tài liệu

Tải lên tài liệu đặc tả để AI đọc nội dung và tạo bộ Test Case tương ứng.

### Sinh Test Case từ giao diện

Tải ảnh giao diện để hệ thống nhận diện các thành phần và sinh Test Case cho từng chức năng.

### Chỉnh sửa Test Case

Có thể chỉnh sửa tiêu đề, tình huống, kết quả mong đợi và các thông tin khác trước khi xuất.

### Sinh lại

Hệ thống hỗ trợ:

- Sinh lại Test Case đang chọn.
- Sinh lại toàn bộ Test Case của một chức năng.

### Xuất Excel

Sau khi hoàn tất, người dùng có thể xuất bộ Test Case thành file Excel để phục vụ kiểm thử.

---

## Kết quả đầu ra

File Excel bao gồm:

- Thông tin dự án
- Tổng hợp Test Case
- Danh sách Test Case theo từng chức năng

---

## Yêu cầu hệ thống

- Python 3.10 trở lên
- Kết nối Internet
- OpenAI API Key hợp lệ

---

## Giấy phép

Dự án được phát triển phục vụ mục đích học tập và nghiên cứu.