# Báo cáo subagent

Thư mục này lưu báo cáo làm việc của các subagent và bằng chứng kiểm thử liên quan. Mục tiêu là giữ report Markdown dễ đọc ở cấp đầu, còn ảnh, audio, video, response thô và log ngắn nằm trong `evidence/`.

## Báo cáo đang hoạt động

- [Backend Builder Report](backend-report.md)
- [Backend Local Speech Fallback - 2026-05-10](backend-local-speech-fallback-report-20260510.md)
- [Backend OpenAI Voice Quality - 2026-05-10](backend-openai-voice-quality-report-20260510.md)
- [Backend Real Video Localization - 2026-05-10](backend-real-video-localization-report-20260510.md)
- [Frontend Builder Report](frontend-report.md)
- [Frontend Redesign Report - 2026-05-10](frontend-redesign-report-20260510.md)
- [Frontend Video Acceptance - 2026-05-10](frontend-video-acceptance-report-20260510.md)
- [Frontend Video Tab Fix - 2026-05-10](frontend-video-tab-fix-report-20260510.md)
- [Frontend Video E2E Fix - 2026-05-10](frontend-video-e2e-fix-report-20260510.md)
- [Infra/Observability Report](infra-report.md)
- [Infra Local Speech Runtime - 2026-05-10](infra-local-speech-runtime-report-20260510.md)
- [Infra Production Secret Guard - 2026-05-10](infra-production-secret-guard-report-20260510.md)
- [Infra Video Environment Runtime - 2026-05-10](infra-video-env-runtime-report-20260510.md)
- [Cloud Production Lifecycle - 2026-05-10](cloud-production-lifecycle-report-20260510.md)
- [Product Architecture Report](product-architecture-report.md)
- [QA Acceptance Report](qa-report.md)
- [QA Public Runtime Acceptance - 2026-05-10](qa-public-runtime-20260510.md)
- [Release Runtime Gate - 2026-05-10](release-runtime-gate-20260510.md)
- [Completion Audit - 2026-05-10](completion-audit-20260510.md)
- [Completion QA Acceptance Audit - 2026-05-10](completion-qa-audit-20260510.md)
- [PM Artifact Completion Audit - 2026-05-10](pm-artifact-completion-audit-20260510.md)
- [Infra Production Completion Audit - 2026-05-10](infra-production-completion-audit-20260510.md)
- [Tech Lead Runtime Review - 2026-05-10](techlead-runtime-review-20260510.md)
- [Tech Lead Release Review - 2026-05-10](techlead-release-review-20260510.md)
- [Skill Author A Report](skill-author-a-report.md)
- [Skill Author B Report](skill-author-b-report.md)

## Bằng chứng runtime

- [evidence/images](evidence/images/) - ảnh chụp Playwright, mobile/desktop, review cuộn trang; bằng chứng PM mới dùng prefix `pm-`, ví dụ `pm-redesign-*`, `pm-scroll-*`, `pm-openai-*`.
- Bằng chứng video mới nhất: [frontend-video-e2e-real-submit-fixed-20260510.png](evidence/images/frontend-video-e2e-real-submit-fixed-20260510.png), [pm-premium-public-video-tab-20260510.png](evidence/images/pm-premium-public-video-tab-20260510.png), các ảnh `frontend-premium-*-video-*`, và video/subtitle `final-gate-video-*` trong `evidence/video/`.
- [evidence/audio](evidence/audio/) - file WAV từ TTS và video localization.
- [evidence/video](evidence/video/) - MP4 nguồn/kết quả và phụ đề SRT/VTT.
- [evidence/api](evidence/api/) - response TXT/JSON, browser-check JSON, bundle JS dùng làm bằng chứng.
- [evidence/qa-audit-20260510](evidence/qa-audit-20260510/) - bằng chứng audit hoàn tất mới nhất: health/readiness, OpenAI TTS, video tiếng Anh/Trung, auth, billing disabled, MLflow nội bộ, test output và deploy blocker.

## Quy ước từ giờ trở đi

- Giữ report chính dạng Markdown ở ngay `docs/subagents/`, đặt tên theo vai trò hoặc mục kiểm thử, ví dụ `qa-public-runtime-YYYYMMDD.md`.
- Không đặt ảnh, audio, video, subtitle, response thô, bundle, log hoặc file dump mới ở root `docs/subagents/`; đưa vào đúng thư mục con dưới `evidence/`.
- Khi report trích dẫn bằng chứng, dùng đường dẫn tương đối tới `evidence/...` để link còn mở được sau khi di chuyển.
- Nếu một report cũ không còn là nguồn đọc chính nhưng vẫn cần giữ, chuyển sang `archive/` kèm link từ README trước khi di chuyển.
- Không xóa bằng chứng runtime nếu chưa có report mới hơn thay thế và chưa ghi rõ lý do.
