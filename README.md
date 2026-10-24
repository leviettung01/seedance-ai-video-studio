# 🎬 Seedance AI Video Studio PRO v5.0
### Hệ Thống Tự Động Hóa Tạo Video 30s Không Watermark — Model Dreamina Seedance 2.5 Pro
*Bản quyền & Phát triển: **Lê Việt Tùng***

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Automation](https://img.shields.io/badge/Automation-Playwright%20%2F%20CDP-red.svg)](https://playwright.dev/)
[![Engine](https://img.shields.io/badge/Engine-Dreamina%20Seedance%202.5%20Pro-orange.svg)](https://www.dola.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## 🌟 Tổng Quan (Overview)

**Seedance AI Video Studio PRO** là giải pháp toàn diện cho việc tự động hóa sản xuất video AI 30 giây chất lượng cao nhất trên nền tảng **ByteDance / Dola AI**. Hệ thống kết hợp giao diện Desktop **PyQt6**, máy chủ nền **FastAPI**, công nghệ can thiệp luồng mạng **Chrome DevTools Protocol (CDP)** và **Chrome Extension** độc quyền giúp:

1. **Khóa cứng thời lượng 30 giây (Hard-Lock 30s):** Ép server render trọn vẹn 30 giây với tham số `duration: 31` và Engine `seedance_v2.5`, triệt tiêu hoàn toàn lỗi bị hạ cấp về 15s.
2. **Tải video không Watermark (Watermark-Free TOS):** Tự động bắt gói tin, giải mã đường dẫn video gốc từ ByteDance TOS và tải video sạch 1080p không logo.
3. **Quản lý đa tài khoản & VIA Facebook:** Quản lý hàng chục tài khoản Dola/FB đồng thời với cơ chế lưu cookie và phân tách profile Chrome riêng biệt (mỗi tab 1 port CDP riêng từ `9230+`).
4. **Hỗ trợ tự động hóa cho AI Agent:** Tích hợp sẵn REST API (`http://127.0.0.1:8899`) và tài liệu chi tiết [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md) cho phép các AI Agent (Antigravity, Claude, ChatGPT, AutoGen, CrewAI...) gọi lệnh tự động.

---

## 📁 Cấu Trúc Thư Mục Dự Án (Repository Structure)

```
seedance-ai-video-studio/
├── Chay_Seedance_Studio.bat          # 🚀 Script khởi động 1-click cho Windows
├── seedance_ai_video_studio_src/     # 🧠 Mã nguồn chính (PyQt6 GUI + FastAPI + Automation)
│   ├── main_gui_pyqt.py              # Giao diện chính PyQt6 Dark Theme sang trọng
│   ├── main_gui.py                   # Giao diện dự phòng Tkinter
│   ├── api_server.py                 # FastAPI REST API Backend (:8899)
│   ├── browser_manager.py            # Quản lý trình duyệt Chrome & Playwright CDP
│   ├── dola_automation.py            # Logic điều phối giao diện Dola Studio
│   ├── video_downloader.py           # Bộ tải video sạch không watermark
│   ├── account_manager.py            # Quản lý phiên đăng nhập & xoay vòng tài khoản
│   ├── job_manager.py                # Quản lý hàng đợi render video (Job Queue)
│   ├── proxy_manager.py              # Quản lý Proxy / VPN xoay IP chống Shark Block
│   ├── requirements.txt              # Danh sách thư viện Python cần thiết
│   └── style.qss                     # Bộ style giao diện Dark Luxury Theme
├── Dola_Bypass_30s_Viet_Hoa/         # 🧩 Chrome Extension đồng bộ
│   ├── manifest.json                 # Manifest V3 Extension
│   ├── skill-pro-content.js          # Tự động nạp Skill & chọn Pro Native
│   ├── skills/video_30s/SKILL.md     # Kịch bản LeVietTungSkill30s tối ưu hóa
│   └── without watermark/            # Trình trích xuất link video không logo
├── skill file and dola dowloader/     # 📜 File kịch bản tham chiếu độc lập
├── docs/                             # 📚 Tài liệu kỹ thuật chuyên sâu
│   ├── HUONG_DAN_THAO_TAC_VA_BYPASS_30S.md
│   ├── PROJECT_MASTER_GUIDE.md
│   └── SKILL_PRO_30S_GUIDE.md
├── accounts.example.json             # 🔒 Mẫu cấu hình tài khoản (Không lưu credential thật)
├── AI_AGENT_GUIDE.md                 # 🤖 Cẩm nang tích hợp và điều khiển cho AI Agent
└── README.md                         # Tài liệu giới thiệu dự án
```

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng Nhanh

### 1. Yêu cầu hệ thống
- Hệ điều hành: Windows 10/11 (64-bit).
- Trình duyệt: Google Chrome bản mới nhất.
- Môi trường: Python 3.10 trở lên.

### 2. Cài đặt thư viện Python
Mở Terminal trong thư mục `seedance_ai_video_studio_src` và chạy:
```bash
pip install -r seedance_ai_video_studio_src/requirements.txt
```

### 3. Khởi chạy 1-Click
Nhấp đúp chuột vào file:
```bat
Chay_Seedance_Studio.bat
```
Script sẽ tự động giải phóng port 8899 (nếu bị kẹt), tìm kiếm môi trường Python phù hợp và khởi chạy giao diện **Seedance AI Video Studio PRO**.

---

## 🤖 Hướng Dẫn Dành Cho AI Agent (Agentic Automation)

Nếu bạn là một **AI Agent** đang thực thi các tác vụ sinh video tự động, bạn có thể tương tác với hệ thống qua 3 phương thức:

1. **Khởi chạy Tool:** Chạy trực tiếp `Chay_Seedance_Studio.bat`.
2. **Sử dụng REST API:** Khởi động server backend `python -m uvicorn api_server:app --port 8899` và tương tác qua các endpoint `/api/jobs/create`, `/api/jobs/{id}`, `/api/status`.
3. **Quy tắc tạo Prompt 30s:** Áp dụng giao thức **4-Stage Temporal Pacing Protocol** (`0-5s`, `5-15s`, `15-25s`, `25-30s`) được ghi rõ trong tài liệu [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md).

---

## 🧩 Cài Đặt Chrome Extension Bổ Trợ

1. Mở trình duyệt Chrome và truy cập `chrome://extensions/`.
2. Bật chế độ **Developer mode (Chế độ dành cho nhà phát triển)** ở góc trên bên phải.
3. Bấm **Load unpacked (Tải tiện ích đã giải nén)** và chọn thư mục `Dola_Bypass_30s_Viet_Hoa`.
4. Mở tab Dola AI và bấm nút tiện ích trên thanh công cụ để sử dụng các tính năng bypass và auto-skill `LeVietTungSkill30s`.

---

## ⚖️ Giấy phép & Tuyên bố miễn trừ trách nhiệm
- Bản quyền thuộc về **Lê Việt Tùng** (@leviettung01).
- Dự án phục vụ mục đích nghiên cứu công nghệ, tự động hóa sáng tạo nội dung số và tích hợp AI Agent.
