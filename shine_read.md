# Voice AI - Hướng Dẫn Nhanh

## Sản Phẩm Làm Gì?

Voice AI giúp biến video tiếng Trung hoặc tiếng Anh thành gói nội dung tiếng Việt:

- Bản dịch/kịch bản tiếng Việt.
- Phụ đề tiếng Việt dạng SRT/VTT.
- Giọng đọc/lồng tiếng Việt.
- Video MP4 cuối cùng có phụ đề và âm thanh tiếng Việt.
- Nền tảng text-to-speech vẫn có nếu cần tạo audio từ văn bản trực tiếp.

## Kiến Trúc Ngắn Gọn

- Frontend: ứng dụng web để upload video, chọn ngôn ngữ/giọng đọc, xem trạng thái job và tải artifact.
- Backend: FastAPI cung cấp health, voices, synthesize, video localization job, artifact download.
- Local fallback/demo: chạy được không cần Google credentials, tạo transcript/subtitle/video demo để test luồng sản phẩm. Âm thanh beep/tone chỉ được xem là fallback có nhãn rõ ràng, không phải giọng Voice AI thật.
- Google Cloud target: Speech-to-Text cho Anh/Trung, Translation sang Việt, Text-to-Speech cho giọng Việt, Cloud Run/GCS cho production.
- MLflow/logging: ghi lại job id, stage, latency, artifact metadata, lỗi và bằng chứng vận hành.
- FFmpeg/video processing: tách audio, xử lý subtitle/audio, render MP4 cuối cùng. Nếu máy không có `ffmpeg`, demo có thể chỉ tạo artifact riêng hoặc copy video.

## Link Test Hiện Tại

Người dùng thường chỉ cần mở link frontend này để xem tiến độ và test sản phẩm:

- **Frontend chính:** `http://103.27.237.252:4174/`

### Link Kỹ Thuật

| Mục | Link |
| --- | --- |
| Local Frontend dự phòng | `http://localhost:4173/` nếu frontend preview đang chạy |
| Local Backend API docs | `http://localhost:8080/docs` sau khi backend được start |
| MLflow UI | `[PM/Infra cần điền]` |
| Public URL khác | `[PM/Infra cần điền nếu có]` |

## Cách Test Thủ Công Khi Có Link

1. Mở frontend chính: `http://103.27.237.252:4174/`.
2. Kiểm tra trạng thái backend ngay trong UI. Chỉ mở `http://localhost:8080/docs` nếu cần xem kỹ API.
3. Upload một video ngắn tiếng Anh hoặc tiếng Trung.
4. Chọn target tiếng Việt, chọn giọng đọc Việt, bật phụ đề nếu có tùy chọn.
5. Tạo localization job và đợi trạng thái chuyển sang succeeded.
6. Tải/xem các artifact: transcript tiếng Việt, SRT/VTT, audio tiếng Việt, final MP4.
7. Nếu có MLflow/log UI, đối chiếu `job_id`, stage latency, provider, artifact metadata và lỗi nếu có.

Khi test với người dùng, giọng prototype phải đến từ TTS provider thật. Nếu hệ thống chỉ tạo beep/tone vì thiếu credentials provider, hãy xem đó là fallback/demo đã được dán nhãn, không dùng để đánh giá chất lượng Voice AI.

Khi PM hoặc agent chạy tác vụ nặng lặp lại, ưu tiên giới hạn CPU bằng `taskset -c 0-3` nếu môi trường hỗ trợ, ví dụ `pytest`, `npm run build`, Playwright, `ffmpeg`, hoặc `docker build`. Việc này giảm tranh chấp tài nguyên server khi nhiều agent cùng chạy.

PM không nên chỉ chờ agent báo xong. Trong lúc agent chạy, PM cần mở public URL, cuộn UI desktop/mobile, chạy smoke command phù hợp, xem screenshot và báo lỗi sớm.

## Giới Hạn Đã Biết

- Hiện có local fallback/demo; luồng Google STT/Translation/TTS thật cho video vẫn cần cấu hình cloud credentials và provider production.
- Prototype để user testing cần TTS provider thật; beep/tone fallback chỉ dùng khi chưa có credentials và phải được ghi rõ là fallback/demo.
- Backend report ghi nhận `ffmpeg` chưa có trên PATH trong môi trường hiện tại; render MP4 thật cần cài `ffmpeg`.
- Video job hiện tại là demo/local và còn thiếu async worker, durable Cloud Storage, signed URL, quota/rate limit production.
- Frontend report ghi nhận Playwright screenshot/E2E bị chặn do thiếu thư viện hệ thống `libgbm.so.1`.
- Không đưa secret vào doc, log, report, `.env.example`, hay command output. Mọi key phải được truyền qua environment variable và redact thành `[redacted]`.

## Doc Nên Đọc Tiếp

- `docs/project-brief.md`: tổng quan sản phẩm.
- `docs/prd.md`: yêu cầu sản phẩm.
- `docs/api-contract.md`: API contract cho backend/frontend.
- `docs/ai-system-design.md`: thiết kế hệ thống.
- `docs/deployment-runbook.md`: chạy local, deploy, rollback.
- `docs/observability-mlflow.md`: logs, metrics, MLflow.
- `docs/security-privacy.md`: bảo mật, privacy, secret handling.
- `docs/acceptance-checklist.md`: checklist bằng chứng release.
- `docs/tutorial-from-zero-to-production.md`: hướng dẫn từ workspace trống đến production.
- `docs/subagents/`: báo cáo backend, frontend, QA và product architecture.
