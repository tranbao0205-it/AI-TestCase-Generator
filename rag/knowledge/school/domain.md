# DOMAIN: SCHOOL — HỆ THỐNG QUẢN LÝ TRƯỜNG HỌC

## Bối cảnh

Quản lý đăng nhập, sinh viên, lớp học, môn học và điểm.

## Vai trò

- Quản trị viên.
- Giáo viên.
- Sinh viên.

## MODULE: Đăng nhập

### Business Rules
- Người dùng đăng nhập bằng tên tài khoản hoặc email và mật khẩu.
- Tài khoản phải đang hoạt động.
- Giáo viên, sinh viên và quản trị viên vào đúng giao diện theo vai trò.
- Không thông báo chi tiết tài khoản hay mật khẩu sai.

### Validation
- Không bỏ trống tài khoản.
- Không bỏ trống mật khẩu.
- Giới hạn số lần đăng nhập sai nếu có.
- Session hết hạn phải yêu cầu đăng nhập lại.

## MODULE: Quản lý sinh viên
### Business Rules
- Mã sinh viên bắt buộc và duy nhất.
- Họ tên, ngày sinh và lớp là bắt buộc.
- Ngày sinh không được ở tương lai.
- Sinh viên phải thuộc lớp đang hoạt động.
- Không xóa sinh viên đã có điểm hoặc dữ liệu liên quan nếu chưa xử lý ràng buộc.
- Trạng thái gồm Đang học, Bảo lưu, Đã tốt nghiệp hoặc Thôi học.
### Validation
- Mã sinh viên đúng độ dài và định dạng.
- Email sinh viên đúng định dạng.
- Số điện thoại đúng định dạng.
- Không chấp nhận ký tự nguy hiểm.

## MODULE: Quản lý lớp học
### Business Rules
- Mã lớp bắt buộc và duy nhất.
- Tên lớp, khóa học và sĩ số tối đa là bắt buộc.
- Sĩ số tối đa phải lớn hơn 0.
- Không thêm sinh viên vượt sĩ số tối đa.
- Giáo viên chủ nhiệm phải đang hoạt động.
- Không xóa lớp đang có sinh viên.

## MODULE: Quản lý môn học
### Business Rules
- Mã môn bắt buộc và duy nhất.
- Tên môn bắt buộc.
- Số tín chỉ hoặc số tiết phải lớn hơn 0.
- Không xóa môn học đã được phân công hoặc đã có điểm.
- Môn tiên quyết phải tồn tại và không được tạo vòng lặp.
## MODULE: Nhập điểm
### Business Rules
- Chỉ giáo viên được phân công mới được nhập điểm.
- Điểm phải nằm trong thang điểm cấu hình, thường từ 0 đến 10.
- Điểm tổng kết được tính theo công thức cấu hình.
- Không nhập điểm cho sinh viên không thuộc lớp môn học.
- Điểm đã khóa không được sửa nếu không có quyền mở khóa.
- Mọi thay đổi điểm quan trọng phải có Audit Log.

### Validation
- Không nhập chữ hoặc ký tự đặc biệt vào trường điểm.
- Không nhập điểm âm.
- Không nhập điểm vượt thang điểm.
- Kiểm tra số chữ số thập phân.
- Kiểm tra thiếu điểm thành phần bắt buộc.
