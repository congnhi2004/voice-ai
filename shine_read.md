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
- Backend: FastAPI cung cấp health, voices, synthesize, video localization job, artifact download, auth và billing capability.
- Public prototype hiện tại: dùng OpenAI thật cho TTS và video localization ngắn; không phải beep/tone fallback khi test public.
- Local fallback/demo: vẫn có để chạy test/dev khi thiếu credentials provider, nhưng phải được dán nhãn rõ và không dùng để đánh giá chất lượng giọng Voice AI.
- Google Cloud target: Speech-to-Text cho Anh/Trung, Translation sang Việt, Text-to-Speech cho giọng Việt, Cloud Run/GCS cho production nếu nhóm chọn đường Google.
- MLflow/logging: hiện có tracking nội bộ/local cho job id, stage, latency, provider và artifact metadata. Public MLflow qua IP đang trả 403, nên xem là internal-only cho tới khi infra công bố endpoint bảo mật.
- FFmpeg/video processing: tách audio, xử lý subtitle/audio, render MP4 cuối cùng. Runtime public hiện có FFmpeg theo audit 2026-05-10.

## Link Test Hiện Tại

Người dùng thường chỉ cần mở link frontend này để xem tiến độ và test sản phẩm:

- **Frontend chính:** `http://103.27.237.252:4174/`

### Link Kỹ Thuật

| Mục | Link |
| --- | --- |
| Public Frontend chính | `http://103.27.237.252:4174/` |
| Public Backend | `http://103.27.237.252:8080/` |
| Public Backend API docs | `http://103.27.237.252:8080/docs` nếu backend public đang bật docs |
| Local Frontend dự phòng | `http://localhost:4174/` hoặc port preview đang được `scripts/local-services.sh status` báo |
| Local Backend API docs | `http://localhost:8080/docs` sau khi backend được start |
| MLflow nội bộ/local | `http://127.0.0.1:5000/` trên máy chạy service; public `http://103.27.237.252:5000/` đang trả 403 host validation |

## Cách Test Thủ Công Khi Có Link

1. Mở frontend chính: `http://103.27.237.252:4174/`.
2. Kiểm tra trạng thái backend ngay trong UI. Chỉ mở `http://localhost:8080/docs` nếu cần xem kỹ API.
3. Upload một video ngắn tiếng Anh hoặc tiếng Trung.
4. Chọn target tiếng Việt, chọn giọng đọc Việt, bật phụ đề nếu có tùy chọn.
5. Tạo localization job và đợi trạng thái chuyển sang succeeded.
6. Tải/xem các artifact: transcript tiếng Việt, SRT/VTT, audio tiếng Việt, final MP4.
7. Nếu có quyền vào MLflow/log nội bộ, đối chiếu `job_id`, stage latency, provider, artifact metadata và lỗi nếu có.

Khi test với người dùng, giọng prototype phải đến từ TTS provider thật. Nếu hệ thống chỉ tạo beep/tone vì thiếu credentials provider, hãy xem đó là fallback/demo đã được dán nhãn, không dùng để đánh giá chất lượng Voice AI.

Khi PM hoặc agent chạy tác vụ nặng lặp lại, ưu tiên giới hạn CPU bằng `taskset -c 0-3` nếu môi trường hỗ trợ, ví dụ `pytest`, `npm run build`, Playwright, `ffmpeg`, hoặc `docker build`. Việc này giảm tranh chấp tài nguyên server khi nhiều agent cùng chạy.

PM không nên chỉ chờ agent báo xong. Trong lúc agent chạy, PM cần mở public URL, cuộn UI desktop/mobile, chạy smoke command phù hợp, xem screenshot và báo lỗi sớm.

## Giới Hạn Đã Biết

- Public prototype hiện tại đã có TTS OpenAI thật và video localization OpenAI thật cho mẫu ngắn, nhưng vẫn chạy trên Docker/tmux local host, không phải Cloud Run production.
- Google STT/Translation/TTS thật cho production vẫn cần credentials và quyết định provider. Hiện public path là OpenAI.
- Video job public hiện tại xử lý đồng bộ trong request; production còn thiếu async worker, durable Cloud Storage/GCS, signed URL, retry/cancel, quota/rate limit và bằng chứng Cloud Run.
- Billing Stripe chưa cấu hình production; checkout phải tiếp tục bị khóa cho tới khi secrets, webhook lifecycle và entitlement được chứng minh.
- Auth public hoạt động cho prototype, nhưng storage SQLite/local chưa đủ để gọi là identity production cho khách hàng thương mại.
- MLflow có bằng chứng tracking nội bộ/local; public MLflow không mở trực tiếp. Cần quyết định rõ internal-only hay endpoint bảo mật cho operator.
- Playwright/E2E đã có bằng chứng chạy với workaround thư viện hệ thống trong audit 2026-05-10; CI/server thật vẫn nên cài browser dependencies đúng cách.
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
