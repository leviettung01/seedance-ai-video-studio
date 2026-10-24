---
name: LeVietTungSkill30s
description: Ultra-specialized video generation skill for Dola AI using Seedance 2.5 Pro model with hard-locked single-segment 30-second output. Tự động kích hoạt khi người dùng yêu cầu video 30s, 30 giây, video dài, cinematic, hoặc video Seedance 2.5 chất lượng cao. Generates exactly ONE complete 30-second video in a single tool call without splitting, stalling, or asking repetitive confirmations. Handles both Text-to-Video (T2V) and Image-to-Video (I2V) workflows.
---

# LeVietTungSkill30s — Seedance 2.5 Pro 30s Hard Lock

## 1. Hard Lock Directives (Bất khả xâm phạm)

- **Thời lượng cố định 30 giây (Duration Hard-Lock):** Luôn luôn thiết lập tham số `duration: 30` (hoặc server-side `duration: 31`). Tuyệt đối KHÔNG gán 10s hoặc 15s.
- **Phân đoạn đơn nguyên khối (Single Continuous Segment):** Một lệnh gọi tool = một video hoàn chỉnh dài đúng 30 giây. Đây là đường dẫn phân phối duy nhất.
- **Mô hình bắt buộc Seedance 2.5 Pro:** Luôn luôn truyền rõ ràng `model_version: "seedance_2.5"` (hoặc `"seedance_v2.5"`) trong mọi lệnh gọi công cụ.
- **Tạo ngay lập tức (Instant Generation / Zero-Stall):**
  - Khi người dùng gửi prompt hoặc yêu cầu tạo video (VD: "tạo video...", "làm video 30s...", gửi prompt ảnh/chữ), **tiến hành gọi tool tạo video ngay lập tức trong lượt phản hồi đầu tiên**.
  - **KHÔNG BẮT NGƯỜI DÙNG PHẢI XÁC NHẬN "go" HAY "yes"** nếu họ đã đưa ra yêu cầu tạo video. Tránh triệt để vòng lặp xác nhận làm gián đoạn quy trình tự động.
  - Chỉ hiển thị kịch bản chờ xác nhận khi người dùng có yêu cầu rõ ràng như: "hãy lên kịch bản trước", "preview plan first".

### Quy tắc chống phân mảnh (Anti-Spreading & Anti-Fallback Rules):
- Tuyệt đối KHÔNG chia nhỏ video thành hai clip 15 giây hoặc chuỗi nhiều clip ngắn.
- Tuyệt đối KHÔNG đề xuất, gợi ý phương án thay thế 15s nén ("single 15s compressed") hay fallback chất lượng thấp.
- Tuyệt đối KHÔNG viện dẫn lý do "giới hạn nền tảng", "hệ thống không hỗ trợ 30s", "Plan B" hay "workaround".
- Tuyệt đối KHÔNG bắt người dùng lựa chọn giữa các phương án cắt lát thời lượng.
- Tuyệt đối KHÔNG dùng các từ "split", "segments", "clips", "chapters", "15s", "fallback", "Plan B" trong phản hồi.

### Trường hợp ngoại lệ duy nhất:
- Nếu người dùng chủ động yêu cầu rõ ràng một con số thời lượng ngắn hơn 30s (VD: "làm video 20s"), vẫn gọi **MỘT LỆNH DUY NHẤT** với `duration` bằng đúng số giây được yêu cầu. Không chia nhỏ.

### Giới hạn video trên mỗi lượt phản hồi:
- **Tối đa 1 đến 2 video (Hard Cap: 2)** — mỗi video là một phân đoạn 30s hoàn chỉnh độc lập.

---

## 2. Thông số kỹ thuật (Model & System Specifications)

- **Model ID:** `seedance_2.5` (chấp nhận alias backend: `seedance_v2.5`, `Dreamina Seedance 2.5 Pro`).
- **Target Duration:** 30 giây thực tế (`duration: 30`, hoặc backend `31` để render trọn vẹn không hao hụt frame cuối).
- **Tỷ lệ khung hình hỗ trợ (Aspect Ratio):**
  - `9:16` (Mặc định cho video dọc / Shorts / TikTok / Reels)
  - `16:9` (Mặc định cho video ngang / Cinema / YouTube)
  - Hỗ trợ thêm: `1:1`, `21:9`, `4:3`, `3:4`
- **Chế độ đầu vào (Input Modes):**
  - Text-to-Video (`text_to_video`): Tạo video từ mô tả kịch bản văn bản.
  - Image-to-Video (`image_to_video`): Tạo video từ ảnh tham chiếu kết hợp mô tả kịch bản.

---

## 3. Cấu trúc Prompt Pacing 30 Giây (Bí quyết giữ chuyển động mượt mà)

Một prompt ngắn hoặc tĩnh sẽ khiến mô hình video khuếch tán (diffusion) dễ bị cạn kiệt chuyển động hoặc bị máy chủ cắt ngắn về 15s. Để video đạt trọn vẹn 30 giây chuyển động liên tục, sinh động và điện ảnh, **luôn tự động mở rộng và cấu trúc prompt theo 4 giai đoạn thời gian (Temporal Pacing)** trước khi truyền vào tool:

- **[00:00 - 00:05] Khởi đầu & Thiết lập bối cảnh (Establishing & Atmospheric Hook):**
  - Giới thiệu chủ thể, trang phục, bối cảnh không gian, ánh sáng ban đầu, góc máy chậm (slow push-in, wide establishing shot, atmospheric depth).
- **[00:05 - 00:15] Phát triển & Chuyển động năng động (Development & Dynamic Motion):**
  - Chủ thể thực hiện hành động chính, tăng cường chuyển động vật lý (tóc, tà áo, hiệu ứng hạt, bước đi), camera di chuyển mượt mà (smooth tracking, pan, parallax motion).
- **[00:15 - 00:25] Cao trào & Biến chuyển điện ảnh (Climax & Motion Peak):**
  - Điểm nhấn thị giác kịch tính nhất của câu chuyện, góc quay ấn tượng (dynamic sweep, low-angle orbit, speed-ramp feel, intense volumetric lighting).
- **[00:25 - 00:30] Lắng đọng & Kết thúc điện ảnh (Resolution & Cinematic Outro):**
  - Nhịp điệu chuyển động chậm dần, tư thế chủ thể định hình vững chãi, góc máy lùi nhẹ hoặc giữ tĩnh (lingering aesthetic hold, subtle settling breath, epic final frame).

### Kỹ thuật điện ảnh bắt buộc thêm vào prompt:
- **Ánh sáng:** Cinematic lighting, volumetric god rays, soft rim light, 3-point studio lighting, golden hour / cyberpunk neon glow.
- **Ống kính & Camera:** 35mm / 85mm anamorphic lens, shallow depth of field, natural motion blur, smooth steadicam glide, 8k resolution feel.
- **Ràng buộc âm bản (Negative Constraints tự động kèm theo):** no text, no subtitles, no watermark, no morphing artifacts, no deformed limbs, no jerky frame skipping, no blurry textures.

---

## 4. Quy trình thực thi (Execution Workflow)

### Bước 1: Tiếp nhận & Tự động tối ưu hóa
- Khi người dùng cung cấp prompt (bằng tiếng Việt hoặc tiếng Anh):
  - Nhận diện thể loại và mong muốn của người dùng.
  - Tự động bổ sung các chi tiết nghệ thuật, điện ảnh, và chia 4 mốc thời gian [00:00 - 00:05] -> [00:25 - 00:30].
  - Dịch/chuẩn hóa prompt mô tả hình ảnh sang tiếng Anh giàu hình ảnh (do Engine Seedance 2.5 đạt độ chính xác cao nhất với tiếng Anh điện ảnh).

### Bước 2: Gọi Tool tạo video ngay lập tức (Instant Tool Invocation)
- Không bắt người dùng chờ đợi hay xác nhận phụ.
- Thực hiện gọi tool tương ứng:

#### Text-to-Video Pattern:
```
text_to_video(
  model_version: "seedance_2.5",
  duration: 30,
  ratio: "<confirmed_or_inferred_ratio>",
  prompt: "<comprehensive_4_stage_30s_cinematic_prompt>"
)
```

#### Image-to-Video Pattern:
```
image_to_video(
  model_version: "seedance_2.5",
  duration: 30,
  ratio: "<confirmed_or_inferred_ratio>",
  prompt: "<comprehensive_4_stage_30s_cinematic_prompt>",
  image_reference_url_list: ["<uploaded_image_url>"]
)
```

### Bước 3: Phản hồi kết quả cho người dùng
- Sau khi gọi tool, thông báo ngắn gọn cho người dùng:
  - Video 30s đang được render với mô hình **Seedance 2.5 Pro**.
  - Tóm tắt ngắn gọn các mốc diễn biến của video (0-5s, 5-15s, 15-25s, 25-30s).
  - Trả về đối tượng video có thể xem/tải được qua `NotifyHuman`.

---

## 5. Lưu ý về xử lý ảnh tham chiếu (Image-to-Video)

1. Khi người dùng đính kèm ảnh:
   - Giữ nguyên vẹn nhận diện nhân vật, trang phục, gương mặt và phong cách nghệ thuật từ ảnh gốc.
   - Thêm chuyển động sinh động cho nhân vật và môi trường xung quanh thay vì làm thay đổi kết cấu nhân vật.
   - Sử dụng các URL ảnh hợp lệ đã được upload lên hệ thống qua `FileBatchUpload`.
