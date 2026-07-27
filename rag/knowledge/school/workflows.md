# WORKFLOW NGHIỆP VỤ TRƯỜNG HỌC

## Workflow: Thêm sinh viên vào lớp

### Vai trò

- Quản trị viên.
- Nhân viên đào tạo.

### Điều kiện trước

- Người dùng đã đăng nhập.
- Lớp đang hoạt động.
- Lớp chưa vượt sĩ số tối đa.

### Luồng chính

1. Mở danh sách sinh viên.
2. Chọn Thêm mới.
3. Nhập mã sinh viên, họ tên, ngày sinh và lớp.
4. Hệ thống kiểm tra mã không trùng.
5. Hệ thống kiểm tra lớp và sĩ số.
6. Người dùng lưu.
7. Hệ thống tạo sinh viên.
8. Hệ thống cập nhật sĩ số lớp.
9. Hệ thống quay lại danh sách.

### Nhánh lỗi

- Mã sinh viên trùng.
- Ngày sinh ở tương lai.
- Lớp không tồn tại.
- Lớp đã đủ sĩ số.
- Người dùng không có quyền.

## Workflow: Nhập và khóa điểm

### Vai trò

- Giáo viên.
- Quản trị viên đào tạo.

### Điều kiện trước

- Giáo viên được phân công môn học.
- Sinh viên thuộc lớp môn học.
- Bảng điểm chưa khóa.

### Luồng chính

1. Giáo viên mở danh sách lớp môn học.
2. Chọn sinh viên.
3. Nhập điểm thành phần.
4. Hệ thống kiểm tra thang điểm.
5. Hệ thống tính điểm tổng kết.
6. Giáo viên lưu.
7. Người có quyền khóa bảng điểm.
8. Hệ thống chuyển trạng thái sang Đã khóa.
9. Sinh viên xem kết quả.

### Test Case bắt buộc

- Nhập điểm hợp lệ.
- Điểm âm.
- Điểm vượt thang.
- Thiếu điểm bắt buộc.
- Giáo viên không được phân công.
- Sửa điểm sau khi khóa.
- Hai giáo viên cùng sửa.
- Lỗi khi tính điểm tổng kết.
- Kiểm tra Audit Log.
