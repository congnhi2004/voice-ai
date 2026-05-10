# Voice AI - handoff sau khi restart

Đọc file này đầu tiên sau khi server restart hoặc sau khi `git pull`.

## Prompt dùng ngay cho agent sau

Copy toàn bộ prompt ở [NEXT_AGENT_PROMPT.md](/home/jhao/code/voice-ai/NEXT_AGENT_PROMPT.md). Nếu file đó bị thiếu, dùng bản rút gọn dưới đây:

```text
Bạn là PM AI Agent cho repo /home/jhao/code/voice-ai.

Nhiệm vụ: tiếp tục đưa sản phẩm Voice AI lên mức production: text-to-speech giọng Việt thật và localize video tiếng Anh/Trung sang kịch bản tiếng Việt, phụ đề, audio lồng tiếng và MP4 cuối.

Luật bắt buộc của user:
- PM chỉ điều phối, kiểm chứng, review và handoff. Không trực tiếp sửa product code/docs trừ khi user đổi luật.
- Trước quyết định docs/UI/implementation/deploy phải web search hoặc đọc official docs hiện hành; coding/library work phải dùng Context7. Không lạm dụng Exa.
- Dùng subagents song song với role name rõ ràng, skill rõ ràng, write scope tách biệt và report path. Các skill liên quan: voice-ai-pm-orchestrator, voice-ai-frontend-builder, voice-ai-backend-builder, voice-ai-infra-observability, voice-ai-product-docs, voice-ai-qa-acceptance, voice-ai-techlead-reviewer.
- Tài liệu tiếng Việt phải có dấu ngay từ bản đầu.
- Tiến độ visual chỉ tính frontend public link và ảnh chụp/smoke thật; không chỉ dựa vào local tests.
- Lệnh nặng dùng taskset -c 0-3 khi khả thi. Không expose secrets. Giữ Docker/disk sạch.
- Khi có thể, commit/push handoff trước restart server. Nếu HTTPS push lỗi auth, để user push từ terminal đã đăng nhập.

Những lỗi cần tránh:
- Đã deploy/review UI yếu quá sớm; UI vẫn giống internal console. Phải review bằng screenshot desktop/mobile và public link trước khi nói tốt.
- Có lúc không verify public link sau build. Mỗi build phải curl public HTML và mở/chụp frontend public.
- Đừng tin tests một mình; phải có API smoke, browser smoke và screenshot.
- Đã thử Docker rebuild khi backend image mất, gặp Docker daemon EOF/apt hang; compose còn vô tình start build voice-ai:local. Trước khi build phải kiểm tra docker ps/images/system df/process.
- Backend public từng down. Khôi phục backend trước rồi mới smoke frontend flow end-to-end.
- Docs không được mất dấu tiếng Việt. Subagent name phải là role name, không đặt tên mơ hồ.
```

## Trạng thái hiện tại cần biết

Frontend public URL:

- `http://103.27.237.252:4174/`
- Đây là link quan trọng nhất để user thấy tiến độ visual. Local preview hoặc ảnh chưa deploy không đủ.
- Public HTML đã từng trỏ tới:
  - `/assets/index-CPkM3X2O.js`
  - `/assets/index-BSQREeFd.css`
- Evidence public UI đã có:
  - `docs/subagents/evidence/images/pm-public-premium-overhaul-desktop-20260510.png`
  - `docs/subagents/evidence/images/pm-public-premium-overhaul-mobile-20260510.png`
  - `docs/subagents/evidence/images/pm-public-premium-overhaul-tts-result-20260510.png`

Backend/infra:

- Backend và infra agents đã implement async video job lifecycle, Cloud Tasks dispatch path, GCS-capable storage helpers, Cloud Run deploy hardening và reports.
- Reports nên đọc trước khi giao việc:
  - `docs/subagents/backend-async-storage-production-report-20260510.md`
  - `docs/subagents/infra-cloud-production-hardening-20260510.md`
- Backend tests từng pass: `taskset -c 0-3 env PYTHONPATH=. .venv/bin/pytest tests/backend -q` -> `40 passed, 3 skipped, 3 warnings`.
- Frontend từng pass lint/unit/build/e2e: `14 passed`.
- Backend public đã down trong handoff vì backend Docker image bị mất khi đang rebuild.

## Lỗi đã xảy ra và cách tránh

- UI được deploy/review quá sớm khi vẫn yếu và giống internal console. Lần sau phải review bằng public URL, desktop/mobile screenshots, scroll thật và text/UI polish trước khi báo tiến độ tốt.
- Không phải lúc nào cũng verify public link sau build. Sau mỗi build/deploy frontend, chạy `curl` public HTML, xác nhận asset mới và chụp screenshot public.
- Tests pass không đủ. Cần ít nhất API smoke, browser smoke, screenshot, và nếu là TTS/video thì artifact playback check.
- Docker rebuild sau khi backend image mất đã gặp Docker daemon EOF và apt network hang. Không retry mù; kiểm tra daemon, disk, images, build process và network trước.
- `docker compose` từng vô tình start build cho `voice-ai:local`. Khi backend image đang thiếu, dùng `--no-build` nếu chỉ muốn start service có image sẵn.
- Backend public đã down. Khôi phục backend health trước khi đánh giá flow frontend.
- Codex chưa push được vì HTTPS auth. Official GitHub docs đã được parent kiểm tra: HTTPS push cần credential/token/Git Credential Manager; `git push -u origin main` set upstream. Nếu lỗi auth, user phải push từ terminal đã đăng nhập.
- Docs tiếng Việt từng có nguy cơ mất dấu. Tài liệu tiếng Việt phải có dấu đầy đủ.
- Subagent names cần có role name và skill, ví dụ `Frontend Builder - Premium UI`, `Backend Builder - API Recovery`, `QA Acceptance - Public Smoke`.
- Không lạm dụng Exa. Dùng web/official docs cho quyết định mới, Context7 cho library/coding, Exa chỉ khi cần research rộng.

## Checklist 15 phút đầu sau restart

1. Vào repo và xem trạng thái, không revert thay đổi của người khác:

```bash
cd /home/jhao/code/voice-ai
git status --short --branch
git remote -v
```

2. Đọc nhanh handoff và reports:

```bash
sed -n '1,240p' AGENT_RESTART_HANDOFF.md
sed -n '1,220p' NEXT_AGENT_PROMPT.md 2>/dev/null || true
sed -n '1,220p' docs/subagents/backend-async-storage-production-report-20260510.md
sed -n '1,220p' docs/subagents/infra-cloud-production-hardening-20260510.md
```

3. Kiểm tra secrets local, không in giá trị:

```bash
test -f .env.runtime && echo ".env.runtime exists" || echo "restore .env.runtime from secure notes"
chmod 600 .env.runtime 2>/dev/null || true
```

4. Kiểm tra Docker/disk/process trước khi restart hoặc build:

```bash
df -h /
docker ps -a
docker images
docker system df
ss -ltnp '( sport = :4174 or sport = :8080 or sport = :5000 )' || true
ps -eo pid,ppid,stat,comm,args | rg 'docker build|docker-buildx|apt-get update|pip install|vite preview|uvicorn|mlflow' || true
```

5. Nếu backend image còn tồn tại, restart không build:

```bash
FORCE_FRONTEND_BUILD=0 FRONTEND_MODE=preview taskset -c 0-3 ./scripts/local-services.sh restart
./scripts/local-services.sh status
```

6. Nếu backend image thiếu, đừng rebuild ngay. Giao `Backend/Infra Recovery` subagent kiểm tra daemon/network/disk và đề xuất một đường phục hồi: build lại một image duy nhất hoặc chạy host venv tạm bằng `.venv`, `.env.runtime`, port `8080`.

7. Verify public/API trước khi báo tiến độ:

```bash
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/v1/product/capabilities
curl -fsS http://103.27.237.252:4174/ | sed -n '1,35p'
```

8. Mở `http://103.27.237.252:4174/`, chụp desktop/mobile screenshots, kiểm tra không overflow, generate TTS ngắn, nghe artifact nếu có.

9. Sau khi service ổn mới dọn Docker:

```bash
docker builder prune -f
docker image prune -f
docker system df
```

Không xóa `ghcr.io/mlflow/mlflow:v3.12.0` hoặc backend image đang chạy.

## Git/GitHub handoff

Remote:

```bash
origin https://github.com/congnhi2004/voice-ai.git
```

Nguồn auth/push bền vững: parent đã kiểm tra official GitHub docs. HTTPS push cần command-line authentication hoặc token/Git Credential Manager; `git push -u origin main` dùng để set upstream. Nếu Codex gặp `could not read Username for 'https://github.com'`, không đoán credential và không paste secrets; để user push từ terminal đã đăng nhập.

Khi user muốn commit/push, kiểm tra phạm vi trước rồi mới commit. Ví dụ cũ của parent:

```bash
git status --short --branch
git add AGENT_RESTART_HANDOFF.md NEXT_AGENT_PROMPT.md docs/subagents docs/deployment-runbook.md deploy scripts .github frontend requirements.txt tests/backend app
git commit -m "Prepare restart handoff and production hardening updates"
git push -u origin main
```

## Blockers sản xuất còn lại

- Cần khôi phục và verify backend public.
- Cần live Cloud Run/GCS/Secret Manager/Cloud Tasks evidence.
- GitHub push/auth cần terminal đã đăng nhập nếu Codex không có credential.
- Backend async/GCS changes đã test local nhưng chưa được xác nhận chạy trên public backend sau lỗi Docker rebuild.
- Billing chưa production-ready nếu chưa có Stripe config và live checkout/portal evidence.
- MLflow hiện vẫn local/internal; production observability evidence chưa hoàn chỉnh.
