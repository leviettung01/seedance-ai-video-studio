# Skill + Pro — v2.2.0 (LeVietTungSkill30s)

Reload extension tại `chrome://extensions` rồi tải lại tab Dola.

1. Đăng nhập tài khoản Dola và mở chat trống.
2. Popup → Bấm **"Cài Skill & chuẩn bị Pro 30s"**.
3. Chờ thông báo "Đã chọn Pro + Skill"; ô chat sẽ xuất hiện chip **LeVietTungSkill30s**.
4. Nhập prompt (tiếng Việt hoặc tiếng Anh), đính kèm ảnh tham chiếu (nếu có) và nhấn gửi. Skill sẽ tự động tối ưu cấu trúc thời gian 4 giai đoạn (0-5s, 5-15s, 15-25s, 25-30s) và kích hoạt công cụ render video 30 giây ngay lập tức (không bắt xác nhận "go" lòng vòng).
5. Muốn tự động chuẩn bị khi mở chat trống của tài khoản: bật checkbox *"Tự chuẩn bị Skill khi mở chat mới trống"* trong popup.

---

### Các điểm tối ưu của LeVietTungSkill30s:
- **Tên Skill mới:** `LeVietTungSkill30s` (hỗ trợ nhận diện chuẩn và tương thích ngược).
- **Cơ chế Instant Generation (Zero-Stall):** Bỏ triệt để vòng lặp xác nhận phiền toái; khi người dùng gửi prompt, AI Agent sẽ gọi tool tạo video ngay lập tức.
- **Tự động mở rộng Temporal Pacing 30s:** Chia nhịp kịch bản rõ ràng 4 giai đoạn thời gian giúp mô hình diffusion Seedance 2.5 duy trì chuyển động mượt mà xuyên suốt 30s, chống đứng hình, chống cắt ngắn 15s.
- **Khóa cứng Model & Duration:** Buộc tool parameter sử dụng `model_version: "seedance_2.5"` và `duration: 30` (server bound 31), triệt tiêu nguy cơ hạ cấp về 15.04s.
- **Hỗ trợ song ngữ Việt - Anh:** Nhận diện hoàn hảo câu lệnh tiếng Việt ("tạo video 30s", "làm video 30 giây") và tự động biên dịch prompt điện ảnh sang tiếng Anh để bộ render Seedance 2.5 hiểu chính xác nhất.
