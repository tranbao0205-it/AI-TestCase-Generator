# DOMAIN: HOSPITAL — HỆ THỐNG QUẢN LÝ BỆNH VIỆN

## Vai trò

- Quản trị viên.
- Nhân viên tiếp nhận.
- Bác sĩ.
- Thu ngân.
- Bệnh nhân.

## MODULE: Quản lý bệnh nhân

### Business Rules

- Mã bệnh nhân bắt buộc và duy nhất.
- Họ tên, ngày sinh và thông tin liên hệ là bắt buộc theo cấu hình.
- CCCD hoặc số điện thoại không được trùng nếu được dùng làm định danh.
- Ngày sinh không được ở tương lai.
- Hồ sơ bệnh nhân có lịch sử khám không được xóa trực tiếp.

## MODULE: Lịch khám

### Business Rules

- Ngày khám không được ở quá khứ.
- Bác sĩ phải đang làm việc trong khung giờ được chọn.
- Không đặt trùng lịch bác sĩ.
- Không đặt trùng lịch bệnh nhân trong cùng khung giờ.
- Chỉ lịch Chờ khám mới được hủy theo quy định.
- Trạng thái gồm Chờ khám, Đang khám, Hoàn thành, Đã hủy.




## MODULE: Thanh toán viện phí

### Business Rules

- Hóa đơn phải thuộc bệnh nhân và lần khám hợp lệ.
- Tổng tiền phải bằng tổng chi phí dịch vụ sau giảm trừ.
- Không thanh toán trùng hóa đơn.
- Hóa đơn đã thanh toán không được sửa trực tiếp.
- Hoàn tiền phải có quyền và lý do.
- Bảo hiểm y tế phải áp dụng đúng tỷ lệ nếu có.

### Validation

- Số tiền phải lớn hơn hoặc bằng 0.
- Hình thức thanh toán phải hợp lệ.
- Giao dịch thất bại không được đổi trạng thái hóa đơn.
