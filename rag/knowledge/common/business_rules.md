## Ánh xạ Business Rule vào nhóm chức năng

### Nhóm thành công

Test Case thuộc nhóm [Tên chức năng] thành công khi:

- Nghiệp vụ hoàn tất đúng yêu cầu.
- Dữ liệu được lưu hoặc cập nhật chính xác.
- Trạng thái được chuyển đúng.
- Dữ liệu liên quan đồng bộ đầy đủ.
- Không phát sinh lỗi hoặc sai lệch dữ liệu.

### Nhóm không thành công

Test Case thuộc nhóm [Tên chức năng] không thành công khi gặp một trong các trường hợp:

- Validation không hợp lệ.
- Dữ liệu trùng.
- Sai định dạng.
- Vượt giới hạn.
- Không đủ quyền.
- Vi phạm Business Rule.
- Trạng thái không hợp lệ.
- SQL Injection hoặc XSS.
- Lỗi API, database hoặc tích hợp.
- Lưu không thành công.
- Dữ liệu cập nhật không đầy đủ.
- Hệ thống thông báo thành công nhưng kết quả nghiệp vụ sai.

Tất cả Validation, Boundary, Permission, Security, Exception và Integration Error đều nằm trong nhóm không thành công nếu nghiệp vụ chính không hoàn tất.