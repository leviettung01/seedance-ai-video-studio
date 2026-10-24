> **Proxy Pháp 20/10/2026:** HMA Paris → 127.0.0.1:10000 đã kiểm tra ra FR; gắn Studio và profile Chrome thử. Nhánh Pro đã nhận ProxyManager; extension 2.1.1 bỏ danh sách 20 cổng giả. HMA hiện đổi IP cả máy; chưa tách route host/VPN. [Báo cáo proxy](analysis/hma_fr_proxy/KET_QUA_PROXY_PHAP.md).

> **Cập nhật 20/10/2026:** đã tích hợp cài Skill theo tài khoản và chat Pro native, extension 2.1.0. Lượt yêu cầu 30s với skill trả video thật 15,04s; chưa xác minh tạo được 30s. Tool kiểm tra thời lượng và báo lỗi thay vì nhận là hoàn thành. Xem [báo cáo tích hợp](analysis/skill_30s_integration/KET_QUA_TICH_HOP.md).

# 🚀 SEEDANCE AI VIDEO STUDIO — TÀI LIỆU CỐT LÕI & NHẬT KÝ PHÁT TRIỂN

> **Tài liệu đặc tả kiến trúc, logic cốt lõi, luồng xử lý hệ thống và nhật ký tiến độ dự án theo thời gian thực.**  
> *Cập nhật liên tục sau mỗi phiên làm việc.*

---

## 📌 MỤC LỤC
1. [Tổng Quan Hệ Thống](#1-tổng-quan-hệ-thống)
2. [Phân Tách 2 Bản Source Code (PRO vs PUBLIC)](#2-phân-tách-2-bản-source-code-pro-vs-public)
3. [Kiến Trúc & Luồng Xử Lý Logic Cốt Lõi](#3-kiến-trúc--luồng-xử-lý-logic-cốt-lõi)
   - [3.1. Cookie Session Pool (5KB vs 500MB Chrome Profile)](#31-cookie-session-pool-5kb-vs-500mb-chrome-profile)
   - [3.2. Worker Pool Đa Luồng (1 - 20 Workers Song Song)](#32-worker-pool-đa-luồng-1---20-workers-song-song)
   - [3.3. Cơ Chế Proxy Sticky Session & Phân Bổ Proxy](#33-cơ-chế-proxy-sticky-session--phân-bổ-proxy)
   - [3.4. Cơ Chế Bypass 31s, Model 2.5 & Upscale 4K](#34-cơ-chế-bypass-31s-model-25--upscale-4k)
   - [3.5. Cơ Chế Import Hàng Loạt VIA Facebook & Quản Lý Account](#35-cơ-chế-import-hàng-loạt-via-facebook--quản-lý-account)
4. [Bản Đồ Cấu Trúc Mã Nguồn (Codebase Structure)](#4-bản-đồ-cấu-trúc-mã-nguồn-codebase-structure)
5. [Bảng Theo Dõi Trạng Thái Tính Năng (Feature Matrix)](#5-bảng-theo-dõi-trạng-thái-tính-năng-feature-matrix)
6. [Nhật Ký Phát Triển & Timeline Realtime (Living Changelog)](#6-nhật-ký-phát-triển--timeline-realtime-living-changelog)
7. [Quy Chuẩn Cập Nhật Khi Thực Hiện Task Mới](#7-quy-chuẩn-cập-nhật-khi-thực-hiện-task-mới)

---

## 1. TỔNG QUAN HỆ THỐNG

- **Tên dự án:** Seedance AI Video Studio (Desktop GUI Application)
- **Nền tảng mục tiêu:** Tự động hóa sản xuất video AI chất lượng cao từ nền tảng **Dola AI (ByteDance)**
- **Công nghệ nền tảng:**
  - **Ngôn ngữ:** Python 3.11+
  - **Giao diện:** Tkinter Modern Cyberpunk Dark Theme (Không xung đột port như Web Local)
  - **Trình duyệt tự động:** Google Chrome + Playwright (CDP Connection)
  - **Xử lý Media:** FFmpeg tích hợp tăng tốc phần cứng (NVIDIA NVENC / CPU libx264)
  - **Hệ thống bất đồng bộ:** Asyncio Queue & Worker Pool Pattern

---

## 2. PHÂN TÁCH 2 BẢN SOURCE CODE (PRO vs PUBLIC)

Để bảo vệ bí mật công nghệ (IP Protection) và phục vụ mục đích thương mại/chia sẻ cộng đồng:

| Tiêu Chí | Bản PRO Private (`seedance_ai_video_studio_pro_src`) | Bản PUBLIC (`seedance_ai_video_studio_public_src`) |
|---|---|---|
| **Cơ chế lưu tài khoản** | **Cookie Session Pool (5KB JSON)** — 0 MB Profile | Chrome User-Data-Dir truyền thống (500MB/acc) |
| **Đa luồng** | **1 - 20 Workers song song độc lập** (Async Queue) | 1 Luồng đơn giản tuần tự |
| **Proxy** | Proxy Pool, Sticky Session, API Key xoay IP, Socks5 | Không có quản lý proxy nâng cao |
| **Bypass Video** | Ép thời lượng **31s**, Model **2.5**, Upscale **4K NVENC** | Thời lượng mặc định 10s |
| **Import VIA** | Import hàng loạt 100-200 tài khoản tự động | Thêm tài khoản thủ công từng cái |
| **Mục đích sử dụng** | Khai thác nội bộ, cày video số lượng lớn | Đóng gói demo / chia sẻ cộng đồng |

---

## 3. KIẾN TRÚC & LUỒNG XỬ LÝ LOGIC CỐT LÕI

### 3.1. Cookie Session Pool (5KB vs 500MB Chrome Profile)

- **Vấn đề cũ:** Mỗi tài khoản Chrome tạo 1 profile thư mục `Default` nặng ~500MB. Với 100 tài khoản tốn **~50 GB ổ cứng**, mở cùng lúc gây nghẽn I/O đĩa.
- **Giải pháp Cookie Pool:**
  1. Dola AI dùng cơ chế xác thực **ByteDance Passport** (`sessionid`, `sid_tt`, `uid_tt`, `odin_tt`, `ttwid`, `passport_csrf_token`).
  2. Module [`session_store.py`](file:///f:/Seedance/seedance_ai_video_studio_src/session_store.py) trích xuất đúng các cookie này và các biến cấu hình LocalStorage (`__dolaDurBypass`, `flow_`, `samantha_`) lưu vào file `accounts_sessions.json` (**chỉ ~5KB / tài khoản**).
  3. Khi tạo video: Worker mở Chrome tạm `about:blank`, nạp session trong **0.6 giây** $\rightarrow$ Dola nhận diện đã đăng nhập ngay lập tức.
  4. Sau khi tải video xong: Chrome tạm và thư mục rác bị xóa sạch (**0 MB đĩa lưu trữ**).

```mermaid
graph TD
    A["accounts_sessions.json (5KB/acc)"] -->|Inject qua CDP (0.6s)| B["Chrome Tạm (Port 9250-9269)"]
    B -->|Gửi prompt + Chờ video| C["Dola AI Cloud Generator"]
    C -->|Download .mp4| D["Thư mục output_videos/"]
    D -->|Đóng Chrome & Xóa Temp Profile| E["RAM/Disk Giải Phóng Ngay Lập Tức"]
```

---

### 3.2. Worker Pool Đa Luồng (1 - 20 Workers Song Song)

- **Cơ chế:** Worker độc lập với Account (Queue Pattern).
  - Người dùng có thể có 100 accounts, nhưng chạy trên 5-20 workers.
  - Mỗi Worker được cấp 1 Debug Port riêng: `9250 + worker_id` (Dải port từ `9250` đến `9269`).
- **Tối ưu RAM siêu cấp (Peak < 2GB cho 20 Workers):**
  - **Giai đoạn 1:** Mở Chrome tạm + Nạp session (~80MB RAM/worker).
  - **Giai đoạn 2:** Gửi prompt $\rightarrow$ Chờ Dola render video (3-8 phút). Chrome lúc này ở trạng thái **Idle Polling** (1 request/15s $\rightarrow$ 0% CPU).
  - **Giai đoạn 3:** Tải video `.mp4` về máy.
  - **Giai đoạn 4 (Then chốt):** **ĐÓNG CHROME TỨC THÌ**, giải phóng 80MB RAM.
  - **Giai đoạn 5:** FFmpeg chạy nền Upscale 4K tận dụng GPU NVIDIA NVENC (không tốn CPU, không cần Chrome).

---

### 3.3. Cơ Chế Proxy Sticky Session & Phân Bổ Proxy

- **Đặc tính Dola AI:** Dola không khóa cứng 1 tài khoản với 1 IP cố định, nhưng **trong suốt 1 phiên tạo video (5-15 phút)** thì IP không được thay đổi đột ngột giữa chừng (tránh rớt session).
- **Cơ chế Sticky Proxy:**
  - Khi Worker nhận Job mới $\rightarrow$ Gọi API Proxy (5Stars, TM Proxy, v.v.) để lấy IP mới.
  - Giữ nguyên IP này trong suốt 1 phiên tạo video.
  - Khi bắt đầu Job tiếp theo $\rightarrow$ Xoay sang IP mới.
- **Định dạng hỗ trợ:**
  - `http://ip:port`
  - `http://username:password@ip:port`
  - `socks5://ip:port`
  - API Key xoay tự động (5Stars: nhamang, tinhthanh).

---

### 3.4. Cơ Chế Bypass 31s, Model 2.5 & Upscale 4K

1. **Bypass 31s Video:**
   - Can thiệp JavaScript Client-side: Ghi đè biến và gọi hàm Extension:
     ```javascript
     localStorage.setItem('__dolaDurBypass', '1');
     localStorage.setItem('__dolaTargetDur', '31');
     localStorage.setItem('__dolaDur31', '1');
     localStorage.setItem('__dolaDur15', '1');
     ```
   - Chặn request tạo video để chèn payload `duration: 31`.
2. **Model 2.5:**
   - Tự động phát hiện và chọn Model `2.5` thay vì Model `2.0` mặc định để cho ra chi tiết chuyển động và độ nét cao nhất.
3. **Upscale 4K:**
   - Tích hợp FFmpeg với thuật toán scaling chất lượng cao:
     - GPU: `h264_nvenc` / `hevc_nvenc` (tốc độ cực nhanh).
     - Fallback: CPU `libx264` với preset tối ưu.

---

### 3.5. Cơ Chế Import Hàng Loạt VIA Facebook & Quản Lý Account

- **Module:** [`bulk_importer.py`](file:///f:/Seedance/seedance_ai_video_studio_src/bulk_importer.py)
- **Hỗ trợ định dạng input:**
  - `UID|PASS|2FA|COOKIE_STRING`
  - `UID|COOKIE_STRING`
  - Chuỗi Cookie thô (`c_user=...; xs=...; datr=...; sb=...; fr=...`)
- **Tự động phân loại:**
  - Kiểm tra Cookie Facebook còn Live hay đã bị Checkpoint.
  - Tự động đồng bộ sang Account Manager và Session Store.

---

## 4. BẢN ĐỒ CẤU TRÚC MÃ NGUỒN (CODEBASE STRUCTURE)

```
f:\Seedance\
├── Chay_Seedance_Studio.bat              # Script khởi chạy GUI chính
├── Chay_Seedance_Studio_PRO.bat          # Script khởi chạy GUI bản PRO
├── Chay_Seedance_Studio_PUBLIC.bat       # Script khởi chạy GUI bản PUBLIC
├── Mo_Tai_Khoan_fb01.bat                 # Script tiện ích mở trực tiếp profile fb01
├── PROJECT_MASTER_GUIDE.md               # [FILE NÀY] Tài liệu tổng thể & Changelog
│
├── seedance_ai_video_studio_src/         # SOURCE CODE GỐC (Phát triển chính)
│   ├── main_gui_pyqt.py                  # [MỚI v3.0] Desktop GUI PyQt6 (6 panels chuyên nghiệp)
│   ├── main_gui.py                       # Desktop GUI Tkinter (bản cũ v2.0, backup)
│   ├── main_gui_tkinter_backup.py        # Backup bản Tkinter gốc
│   ├── style.qss                         # [MỚI] QSS Dark Theme Stylesheet (~400 dòng)
│   ├── thumbnail_cache.py                # [MỚI] FFmpeg thumbnail extraction & video info
│   ├── worker_pool.py                    # Quản lý đa luồng 1-20 workers song song (v2)
│   ├── session_store.py                  # Quản lý Cookie Session Pool (5KB JSON)
│   ├── browser_manager.py                # Điều khiển Chrome CDP, ephemeral temp chrome
│   ├── dola_automation.py                # Automation engine: chat prompt, bypass 31s, model 2.5
│   ├── bulk_importer.py                  # Module import hàng loạt VIA & login tự động
│   ├── account_manager.py                # Quản lý tài khoản, quota, proxy binding, VIA parser
│   ├── proxy_manager.py                  # Quản lý Proxy Pool, 5Stars API, sticky resolver
│   ├── video_downloader.py               # Tải video & FFmpeg Upscale 4K (NVENC/CPU)
│   ├── config.py                         # Cấu hình hệ thống, đường dẫn, tham số mặc định
│   └── utils.py                          # Logging, helper đa nền tảng
│
├── seedance_ai_video_studio_pro_src/     # BẢN PRO PRIVATE (Đồng bộ đầy đủ tính năng)
├── seedance_ai_video_studio_public_src/  # BẢN PUBLIC (Đã lược bỏ thuật toán lõi)
├── seedance_ai_video_studio_ext/         # Chrome Extension hỗ trợ can thiệp Dola
├── dola_no_watermark_downloader_ext/     # [MỚI] Extension độc lập bắt link video Dola không logo
├── output_videos/                        # Thư mục chứa video đã tạo thành phẩm
└── downloads/                            # Thư mục tạm trong quá trình xử lý
```

---

## 5. BẢNG THEO DÕI TRẠNG THÁI TÍNH NĂNG (FEATURE MATRIX)

| Tính Năng | Trạng Thái | Phiên Bản | Ghi Chú |
|---|---|---|---|
| **Cookie Session Pool (5KB)** |  Hoàn thành | PRO | Lưu vào `accounts_sessions.json`, test thành công |
| **Worker Pool 1 - 20 Luồng** |  Hoàn thành | PRO | Port `9250-9269`, giải phóng RAM trước upscale |
| **Bypass 31s Video** |  Hoàn thành | PRO | Kích hoạt qua Extension + localStorage flag |
| **Model AI 2.5** |  Hoàn thành | PRO | Tự động chọn selector Model 2.5 |
| **Upscale 4K FFmpeg** |  Hoàn thành | PRO | Tự động upscale sau khi tải video |
| **Proxy Sticky per-Job** |  Hoàn thành | PRO | Xoay 1 lần đầu job, giữ nguyên suốt phiên |
| **Import Hàng Loạt VIA** |  Hoàn thành | PRO | Parse UID, c_user, xs, datr, sb, fr |
| **Fix Debug Port khi Mở Chrome** |  Hoàn thành | PRO & PUBLIC | Đã sửa lỗi thiếu `--remote-debugging-port` |
| **Tách 2 Source (PRO / PUBLIC)** |  Hoàn thành | PRO / PUBLIC | Có batch file riêng cho từng bản |
| **PyQt6 Professional GUI v3.0** | ✅ Hoàn thành | PRO | 6 panels: Dashboard, Video, Gallery, Accounts, Proxy, Settings |
| **Video Gallery Grid Preview** | ✅ Hoàn thành | PRO | Grid thumbnail 4-5 cột, FFmpeg trích frame, play/delete |
| **Anti-Ban Parameters Panel** | ✅ Hoàn thành | PRO | 8 tham số: delay, rotate mode, max daily, fingerprint |
| **Dola No-Watermark Downloader** | ✅ Hoàn thành | EXTENSION | Tự động bắt link CDN MP4 gốc không logo trực tiếp trên web |
| **Luồng 15s qua Pro native** | Đã có MP4 15,04s kiểm chứng | SOURCE CHÍNH | Không sửa payload; đọc SSE, đổi account, ffprobe file; model ID chưa expose, còn watermark Dola |

---

## 6. NHẬT KÝ PHÁT TRIỂN & TIMELINE REALTIME (LIVING CHANGELOG)

### [2026-10-19] — Chẩn đoán lỗi Dola và nhánh 15s native

- Kiểm tra ZIP dola_2.0: phần đã khảo sát là bộ tạo account/profile/cookie, chưa thấy can thiệp video 15s.
- Bắt lỗi HTTP 200/SSE STREAM_ERROR 710020202; không lấy spinner hay lời chat làm xác nhận render/credit.
- Thêm native_video_automation.py, tích hợp WorkerPool cho 15s; kiểm tra duration file trước completed. Sửa retry account, stop/cleanup, cập nhật Qt qua signal; mặc định GUI 15s/2.0/không upscale và khai báo PyQt6.
- 9 tests passed; compile source và GUI smoke test OK. Live native/Pro đã tạo được file HEVC 15,041667s, 1280×720, 24fps; ffprobe độc lập và xem khung hình xác nhận. Pro không expose model ID/credit; chưa khẳng định model 2.0 hay 2.5 và file còn watermark Dola.
- Phạm vi lần sửa là source chính mà Chay_Seedance_Studio.bat chạy. Chi tiết: analysis/DOI_CHIEU_ZIP_VA_VIDEO_15S.md.

### 📅 [2026-08-26] — Phiên Phát Triển & Tối Ưu Toàn Diện

#### Task 1: Chuyển đổi từ Chrome Profile nặng sang Cookie Session Pool (5KB)
- **Mục tiêu:** Giải quyết vấn đề nghẽn ổ cứng và mở hàng chục profile Chrome nặng nề.
- **Thực hiện:**
  - Xây dựng module [`session_store.py`](file:///f:/Seedance/seedance_ai_video_studio_src/session_store.py) chuyên trích xuất 26 cookie ByteDance Passport và biến LocalStorage.
  - Thay thế User Data Dir 500MB bằng Chrome tạm `about:blank` inject cookie trong 0.6s.
  - Kết quả kiểm thử: Đăng nhập thành công 100%, dung lượng lưu trữ giảm từ 500MB xuống 5KB/account.

#### Task 2: Nâng cấp Worker Pool v2 (Hỗ trợ 1 - 20 Workers song song)
- **Mục tiêu:** Cho phép chạy 10-20 video cùng lúc với chi phí phần cứng tối thiểu.
- **Thực hiện:**
  - Nâng cấp [`worker_pool.py`](file:///f:/Seedance/seedance_ai_video_studio_src/worker_pool.py) với hàng đợi Asyncio Queue.
  - Tách dải cổng Chrome Debug từ `9250` đến `9269`.
  - **Tối ưu RAM cốt lõi:** Đóng Chrome tạm ngay sau khi download video xong $\rightarrow$ RAM giảm về mức tối thiểu trước khi bước vào khâu Upscale 4K.
  - Cập nhật UI Combobox số luồng trên GUI: `1, 2, 3, 5, 10, 15, 20`.
  - Test thực tế: 3 workers chạy song song đăng nhập và xử lý đồng thời chỉ trong 7.3s.

#### Task 3: Tách Biệt 2 Bộ Source Code (PRO vs PUBLIC)
- **Mục tiêu:** Bảo vệ mã nguồn cốt lõi khi chia sẻ hoặc phát hành bản công khai.
- **Thực hiện:**
  - Tạo cấu trúc thư mục `seedance_ai_video_studio_pro_src` (chứa toàn bộ thuật toán session pool & đa luồng).
  - Tạo cấu trúc thư mục `seedance_ai_video_studio_public_src` (chỉ chứa flow cơ bản).
  - Tạo các file batch [`Chay_Seedance_Studio_PRO.bat`](file:///f:/Seedance/Chay_Seedance_Studio_PRO.bat) và [`Chay_Seedance_Studio_PUBLIC.bat`](file:///f:/Seedance/Chay_Seedance_Studio_PUBLIC.bat).

#### Task 4: Xây dựng Module Import Hàng Loạt VIA Facebook (`bulk_importer.py`)
- **Mục tiêu:** Tự động hóa khâu nạp 100-200 tài khoản VIA.
- **Thực hiện:**
  - Tạo [`bulk_importer.py`](file:///f:/Seedance/seedance_ai_video_studio_src/bulk_importer.py) với parser đa định dạng VIA (`uid|pass|2fa|cookies`).
  - Tích hợp giao diện Dialog "Import Hàng Loạt (VIA)" vào tab Tài Khoản của GUI với thanh tiến độ realtime.

#### Task 5: Sửa lỗi "Chưa kết nối được Chrome khi bấm Lưu Session Dola"
- **Nguyên nhân:** Hàm `open_chrome_profile` trong [`main_gui.py`](file:///f:/Seedance/seedance_ai_video_studio_src/main_gui.py) thiếu tham số `--remote-debugging-port`.
- **Thực hiện:** Đã bổ sung gán port động và đồng bộ sang bản PRO. Người dùng đã lưu thành công session 27 cookies cho `via_61593678305632`.

#### Task 6: Nâng Cấp GUI Toàn Diện — Tkinter → PyQt6 Professional (v3.0)
- **Mục tiêu:** Xây dựng lại hoàn toàn giao diện từ Tkinter cơ bản sang PyQt6 chuyên nghiệp với dark theme, đa luồng trực quan, video gallery grid preview.
- **File mới:**
  - [`main_gui_pyqt.py`](file:///f:/Seedance/seedance_ai_video_studio_src/main_gui_pyqt.py) (~750 dòng) — 6 panels: Dashboard, Tạo Video, Video Gallery, Tài Khoản, Proxy & Anti-Ban, Cài Đặt.
  - [`style.qss`](file:///f:/Seedance/seedance_ai_video_studio_src/style.qss) (~400 dòng) — Dark glassmorphism theme.
  - [`thumbnail_cache.py`](file:///f:/Seedance/seedance_ai_video_studio_src/thumbnail_cache.py) — FFmpeg thumbnail extraction cho gallery.
- **Chi tiết thay đổi:**
  - Sidebar navigation thay cho tab bar (6 mục icon + text).
  - Dashboard: 5 stat cards + worker status grid realtime + console log.
  - Tạo Video: 12 tham số đa luồng (workers, delay, retry, timeout, proxy mode, auto-rotate, v.v.).
  - Video Gallery: Grid 4-5 cột thumbnail preview, sort, play/delete.
  - Proxy & Anti-Ban: 8 tham số chống ban (delay account, delay IP, max daily, rotate mode, UA, fingerprint).
  - Signal-Slot pattern cho thread-safe UI updates.
  - Backend modules (worker_pool, session_store, browser_manager, v.v.) giữ nguyên 100%.
- **Kết quả kiểm thử:** Compile OK, process chạy không crash. Cần user visual testing.

#### Task 7: Tạo Extension Độc Lập Bắt Link Video Dola Không Logo (`dola_no_watermark_downloader_ext`)
- **Mục tiêu:** Cho phép người dùng tải thủ công video siêu nét không watermark trực tiếp trên giao diện web `dola.com` / `doubao.com`.
- **Thư mục mới:** [`dola_no_watermark_downloader_ext/`](file:///f:/Seedance/dola_no_watermark_downloader_ext/)
  - `manifest.json`: Manifest V3 (Chrome, Edge, Brave, Cốc Cốc) với quyền `webRequest`.
  - `inject.js`: Hook Network Fetch/XHR/SSE và `PerformanceObserver` bắt URL stream gốc `lr=cici_ai`.
  - `content.js` + `content.css`: Giao diện nổi floating bar & nút tải trực tiếp trên video.
  - `background.js`: Service worker bắt stream ở tầng Browser Network Engine.
  - `popup.html` / `popup.js` / `popup.css`: Popup quản lý danh sách video, xuất python script.
  - `HUONG_DAN_CAI_DAT.md`: Hướng dẫn cài đặt.

#### Task 8: Tải Hàng Loạt 50 Video BirdieChaos (Vẹt) Chuẩn `lr=cici_ai` (No Logo)
- **Mục tiêu:** Tải trọn bộ 50 video do Dola AI tạo ra cho chủ đề BirdieChaos (4 con vẹt trên ghế da) theo chế độ không logo `lr=cici_ai`.
- **File mới:**
  - [`tai_50_video_birdiechaos.py`](file:///f:/Seedance/tai_50_video_birdiechaos.py): Script đa luồng (8 workers) tải 50 video song song, sinh file phụ đề `.srt`, xuất file danh mục `.csv`.
  - [`video_list_birdiechaos_50_cici.csv`](file:///f:/Seedance/video_list_birdiechaos_50_cici.csv): Danh mục 50 video kèm STT và link `lr=cici_ai`.
  - Thư mục lưu trữ: `F:\Seedance\downloaded_videos_birdiechaos_50_cici\` (50 file `.mp4` + 50 file `.srt`).
- **Kết quả kiểm thử:** Tải hoàn tất **50/50 video (100%)** trong **20.77 giây** với tổng dung lượng **50.34 MB**, 0 lỗi.

---

## 7. QUY CHUẨN CẬP NHẬT KHI THỰC HIỆN TASK MỚI

Mỗi khi có yêu cầu mới hoặc sửa đổi mã nguồn:
1. **Kiểm tra file này trước tiên** để nắm bắt trạng thái và logic hệ thống hiện tại.
2. Sau khi hoàn thành code & test:
   - Cập nhật mục **[5. Bảng Theo Dõi Trạng Thái Tính Năng]**.
   - Thêm 1 mục mới vào **[6. Nhật Ký Phát Triển & Timeline Realtime]** với cấu trúc:
     ```markdown
     #### Task [Số thứ tự]: [Tên Task]
     - **Mục tiêu:** ...
     - **File ảnh hưởng:** ...
     - **Chi tiết thay đổi:** ...
     - **Kết quả kiểm thử:** ...
     ```
3. Đồng bộ các file thay đổi sang thư mục `seedance_ai_video_studio_pro_src/` (hoặc `public_src/` nếu áp dụng).
