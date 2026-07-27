# DOMAIN: RECRUITMENT — HỆ THỐNG QUẢN LÝ TUYỂN DỤNG

## Vai trò

- Quản trị viên.
- HR.
- Người phỏng vấn.
- Ứng viên.

## MODULE: Đăng tin việc làm

### Business Rules

- Tiêu đề, vị trí, mô tả và hạn nộp là bắt buộc.
- Hạn nộp không được ở quá khứ.
- Tin Nháp được sửa.
- Tin Đã đăng được hiển thị cho ứng viên.
- Tin Hết hạn không nhận hồ sơ mới.
- Chỉ HR hoặc Admin được đăng tin.

## MODULE: Ứng tuyển

### Business Rules
- Ứng viên phải có hồ sơ hợp lệ.
- CV là bắt buộc.
- Không ứng tuyển trùng cùng vị trí nếu chưa có quy định cho phép.
- Không ứng tuyển tin đã hết hạn hoặc đã đóng.
- Trạng thái ban đầu là Mới nhận.

## MODULE: Quản lý hồ sơ

### Business Rules

- Hồ sơ phải thuộc một ứng viên.
- Email và số điện thoại phải đúng định dạng.
- CV phải đúng định dạng và giới hạn dung lượng.
- Dữ liệu cá nhân chỉ người có quyền mới được xem.

## MODULE: Lịch phỏng vấn

### Business Rules

- Ứng viên và người phỏng vấn phải tồn tại.
- Ngày phỏng vấn không ở quá khứ.
- Không đặt trùng lịch người phỏng vấn.
- Chỉ hồ sơ phù hợp mới được chuyển sang Phỏng vấn.
- Kết quả phỏng vấn phải được ghi nhận.

## MODULE: Phân quyền

### Business Rules

- HR quản lý tin tuyển dụng, hồ sơ và lịch phỏng vấn.
- Người phỏng vấn chỉ xem hồ sơ được phân công.
- Ứng viên chỉ xem và sửa hồ sơ của mình.
- Admin quản lý tài khoản và quyền.
