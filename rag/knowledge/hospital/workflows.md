# WORKFLOW NGHIỆP VỤ BỆNH VIỆN

## Workflow: Đặt lịch và khám bệnh

### Vai trò

- Nhân viên tiếp nhận.
- Bệnh nhân.
- Bác sĩ.

### Luồng chính

1. Chọn hoặc tạo hồ sơ bệnh nhân.
2. Chọn chuyên khoa và bác sĩ.
3. Chọn ngày và khung giờ.
4. Hệ thống kiểm tra lịch trống.
5. Xác nhận đặt lịch.
6. Lịch chuyển sang Chờ khám.
7. Bệnh nhân đến tiếp nhận.
8. Lịch chuyển sang Đang khám.
9. Bác sĩ ghi chẩn đoán và chỉ định.
10. Lịch chuyển sang Hoàn thành.

### Nhánh lỗi

- Bệnh nhân không tồn tại.
- Ngày khám ở quá khứ.
- Khung giờ đã được đặt.
- Bác sĩ nghỉ.
- Bệnh nhân hủy lịch.
- Không đủ quyền đổi trạng thái.

## Workflow: Kê đơn và thanh toán

### Luồng chính

1. Bác sĩ mở lần khám.
2. Chọn thuốc, liều dùng và số lượng.
3. Hệ thống kiểm tra thuốc và dị ứng.
4. Bác sĩ lưu đơn.
5. Hệ thống tính chi phí.
6. Thu ngân mở hóa đơn.
7. Áp dụng bảo hiểm hoặc giảm trừ.
8. Người bệnh thanh toán.
9. Hóa đơn chuyển sang Đã thanh toán.
10. Hệ thống xuất phiếu thu.

### Test Case bắt buộc

- Kê đơn hợp lệ.
- Thuốc không tồn tại.
- Số lượng âm.
- Cảnh báo dị ứng.
- Thanh toán thành công.
- Thanh toán trùng.
- Giao dịch thất bại.
- Tổng tiền sai.
- Người không có quyền hoàn tiền.
