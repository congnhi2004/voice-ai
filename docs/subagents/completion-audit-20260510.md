# Completion Audit - 2026-05-10

Vai trò: Final Acceptance Audit Agent
Skill dùng: `voice-ai-qa-acceptance`
Repo: `/home/jhao/code/voice-ai`
Phạm vi ghi: chỉ file này và `docs/subagents/release-runtime-gate-20260510.md`. Không sửa code sản phẩm. Không dùng Exa. Context7 không áp dụng vì không sửa code/test. Không dùng web search vì các kết luận hiện tại dựa trên runtime public, git, test command và report/evidence trong repo.

## 1. Kết luận ngắn

Trạng thái audit hiện tại đã khác các báo cáo cũ trước fix. Public TTS demo hiện dùng OpenAI, `/readyz` báo provider `openai` ready, `/v1/voices` có `marin` và `cedar`, `/v1/synthesize` với `marin` trả WAV tải được và có MLflow run id.

Tuy nhiên, không được claim là full production/commercial release. Video localization vẫn là local deterministic demo; auth/billing còn demo; storage vẫn local filesystem; public MLflow qua IP vẫn bị chặn host validation; CI/CD/Cloud Run/GCS/Cloud Tasks production chưa có bằng chứng live đầy đủ; git còn ahead origin và push qua HTTPS vẫn thiếu credential.

## 2. Build và runtime được audit

| Hạng mục | Bằng chứng hiện tại | Kết luận |
| --- | --- | --- |
| Public frontend | `GET http://103.27.237.252:4174/` trả HTTP 200, title `Voice AI Text to Real Voice Studio`, bundle `/assets/index-B3rd-z76.js`. | Đạt cho public UI load. |
| Public backend | `GET http://103.27.237.252:8080/healthz` trả HTTP 200 `{"status":"ok","service":"voice-ai","version":"0.1.0"}`. | Đạt. |
| Runtime env file | `taskset -c 0-3 ./scripts/local-services.sh status` báo `runtime env file: loaded`. | `.env.runtime` đang được nạp ở runtime. |
| Production guard | Status báo `PUBLIC_DEMO_PROFILE: set`, `REQUIRE_REAL_TTS: set`, `OPENAI_API_KEY: set`; không in secret value. | Guard đang bật và không lộ secret qua status. |
| Backend image | Status báo `backend image: voice-ai:durable-20260510`; container `voice-ai-backend` healthy. | Image runtime đã rebuild theo nhánh hiện tại. |
| OpenAPI | `/openapi.json` title `Voice AI TTS API`, version `0.1.0`; có `/v1/synthesize`, `/v1/voices`, `/v1/video-localization/jobs`, auth, product, readiness. | API surface public có thật. |

## 3. Objective-to-evidence matrix

| Yêu cầu | Bằng chứng hiện tại | Quyết định |
| --- | --- | --- |
| Public runtime dùng OpenAI provider | `/readyz`: `provider.name=openai`, `ready=true`; status: `TTS_PROVIDER=set`, `OPENAI_API_KEY=set`, `GOOGLE_APPLICATION_CREDENTIALS=unset`. | Đạt cho public TTS runtime hiện tại. |
| Không lộ OpenAI key | Status chỉ in `set/unset`; audit không đọc hoặc ghi giá trị `OPENAI_API_KEY`. | Đạt trong lượt audit này. |
| `/v1/voices` có `marin`/`cedar` | `GET /v1/voices` trả `provider=openai`, voices gồm `marin`, `cedar`, `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`, `verse`. | Đạt. |
| Public TTS dùng OpenAI/marin | POST `/v1/synthesize` request id `final-acceptance-openai-marin-20260510` trả job `tts_c945f6990f6049d2a9f404df3fb831e2`, `provider.name=openai`, `fallback=false`, model `gpt-4o-mini-tts`, voice `marin`. | Đạt. |
| Audio URL tải được | Audio URL `http://103.27.237.252:8080/audio/tts_c945f6990f6049d2a9f404df3fb831e2.wav`; downloaded file `/tmp/voice-ai-openai-marin.wav` 295,244 bytes; `file` báo RIFF/WAVE PCM 16-bit mono 24 kHz; container `ffprobe` báo duration 6.15s. | Đạt cho TTS demo public. |
| MLflow run id hiện diện | TTS response có `observability.mlflow_run_id=67fafe230e4e4dadb31222777e67e235`, warnings rỗng; `docker logs voice-ai-mlflow` có `runs/create`, `runs/log-batch`, `runs/get`, `runs/update` HTTP 200 cho run này. | Đạt ở backend-to-MLflow nội bộ. |
| Public MLflow truy cập được | `curl http://103.27.237.252:5000/api/3.0/mlflow/server-info` trả HTTP 403 `Invalid Host header`. | Không đạt nếu yêu cầu public observability UI/API. Có thể chấp nhận nếu MLflow là internal-only và được ghi rõ. |
| Frontend redesign/public title | Public HTML có meta description production-style studio và title `Voice AI Text to Real Voice Studio`. | Đạt. |
| Browser-level evidence | Có ảnh evidence hiện có: `docs/subagents/evidence/images/pm-openai-web-smoke-20260510.png`, `pm-redesign-desktop-20260510.png`, `pm-redesign-mobile-20260510.png`, `pm-redesign-tts-success-20260510.png`, `qa-public-desktop-20260510.png`, `qa-public-mobile-20260510.png`. Lượt audit này dùng API TTS flow thay vì chạy lại Playwright. | Đạt cho evidence hiện có cộng API smoke hiện tại. |
| Backend tests | `taskset -c 0-3 env PYTHONPATH=. ./.venv/bin/pytest tests/backend -q`: `21 passed, 3 skipped, 2 warnings in 2.53s`. | Đạt, với 3 skip hiện hữu. |
| Frontend lint/unit/build | `taskset -c 0-3 npm --prefix frontend run lint`: pass. `npm --prefix frontend run test -- --run`: 1 file, 4 tests passed. `npm --prefix frontend run build`: Vite build pass, bundle `index-B3rd-z76.js`, CSS `index-BoKnBMRY.css`. | Đạt. |
| Video localization production | `/v1/product/capabilities` vẫn báo `video_localization.demo_mode=true`; các evidence cũ cho video dùng `provider.local`, `deterministic-video-localization-demo`. | Không đạt production. Chỉ demo/local artifact pipeline. |
| Auth/billing production | `/v1/product/capabilities`: `auth.mode=local-demo`, `production_identity=false`, `billing.available=false`, `production_billing=false`. | Không đạt production/commercial. |
| Durable production storage | Readiness storage `mode=local`; TTS response có `audio_path=/app/data/audio/...`. | Không đạt production storage; cần GCS/durable object storage hoặc policy rõ. |
| Git release/push | `git status --short --branch`: `main...origin/main [ahead 3]`; dry-run push fail `could not read Username for 'https://github.com': terminal prompts disabled`. | Chưa push được từ tool session. |

## 4. Lệnh đã chạy trong lượt audit

```bash
taskset -c 0-3 ./scripts/local-services.sh status
curl -fsS http://103.27.237.252:4174/
curl -fsS http://103.27.237.252:8080/readyz
curl -fsS http://103.27.237.252:8080/v1/voices
curl -fsS -X POST http://103.27.237.252:8080/v1/synthesize \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: final-acceptance-openai-marin-20260510' \
  --data-binary @/tmp/voice-ai-openai-marin-request.json
curl -fsS http://103.27.237.252:8080/audio/tts_c945f6990f6049d2a9f404df3fb831e2.wav -o /tmp/voice-ai-openai-marin.wav
file /tmp/voice-ai-openai-marin.wav
docker exec voice-ai-backend ffprobe -v error -show_entries format=duration:stream=codec_name,codec_type,sample_rate,channels -of json /app/data/audio/tts_c945f6990f6049d2a9f404df3fb831e2.wav
curl -sS -o /tmp/voice-ai-mlflow-server-info.txt -w 'HTTP %{http_code}\n' http://103.27.237.252:5000/api/3.0/mlflow/server-info
docker logs --since 10m voice-ai-mlflow
taskset -c 0-3 env PYTHONPATH=. ./.venv/bin/pytest tests/backend -q
taskset -c 0-3 npm --prefix frontend run lint
taskset -c 0-3 npm --prefix frontend run test -- --run
taskset -c 0-3 npm --prefix frontend run build
git log --oneline origin/main..HEAD
git remote -v
GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD
```

## 5. Gaps còn thật

1. P0 cho production/commercial: video localization chưa dùng STT/translation/dubbing production. Nó vẫn là demo deterministic/local theo product capabilities và evidence hiện có.
2. P0 cho production/commercial: storage vẫn local filesystem; chưa có bằng chứng GCS/durable storage, signed URL policy, retention enforcement, hoặc Cloud Run disposable filesystem mitigation.
3. P1: public MLflow API/UI qua IP vẫn trả 403 host validation. Nếu chọn internal-only thì cần release docs nói rõ đường kiểm chứng nội bộ; nếu public thì cần reverse proxy/auth/allowed-host đúng.
4. P1: auth và billing vẫn demo/local, chưa phù hợp sản phẩm thương mại.
5. P1: chưa có bằng chứng GitHub Actions/Cloud Run production deployment live: không có run URL, image digest promoted, Cloud Run revision/service URL, GCS object proof, Cloud Tasks job proof, rollback evidence.
6. P1: git chưa publish được từ môi trường tool vì remote HTTPS thiếu credential; local branch `main` đang ahead origin 3 commits.
7. P2: các report cũ dưới `docs/subagents/` còn chứa kết luận stale rằng public runtime là local/beep. Hai file audit/gate này thay thế quyết định release hiện tại, nhưng nếu dùng toàn bộ docs làm handoff thì cần đọc theo thời gian.

## 6. Quyết định audit

**Public TTS demo: đạt để user testing có kiểm soát.** Người dùng có thể mở public frontend, tạo TTS qua OpenAI/marin, nhận WAV, tải artifact, và có MLflow run id nội bộ.

**Full production/commercial product: chưa đạt.** Không claim production complete cho đến khi video localization production, storage bền vững, auth/billing thật, observability policy, CI/CD deploy evidence, và push/release hygiene được đóng.
