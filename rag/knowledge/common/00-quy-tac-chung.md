## Quy tắc phân nhóm chức năng

Mọi Test Case bắt buộc thuộc đúng một trong hai nhóm:

- [Tên chức năng] thành công
- [Tên chức năng] không thành công

Không để giá trị Chức năng chỉ là tên hành động chung như:

- Đăng nhập
- Thêm mới
- Cập nhật
- Xóa
- Tìm kiếm

Phải chuyển thành:

- Đăng nhập thành công
- Đăng nhập không thành công
- Thêm mới thành công
- Thêm mới không thành công
- Cập nhật thành công
- Cập nhật không thành công

Test Case được xếp theo kết quả nghiệp vụ cuối cùng, không dựa riêng vào thông báo giao diện.

Ví dụ:

- Hệ thống báo thêm mới thành công và dữ liệu được lưu đúng
  → Thêm mới thành công.

- Hệ thống báo thêm mới thành công nhưng dữ liệu không được lưu
  → Thêm mới không thành công.

- Hệ thống chặn dữ liệu sai và hiển thị cảnh báo đúng
  → Vẫn thuộc [Tên chức năng] không thành công vì nghiệp vụ chính không hoàn tất.