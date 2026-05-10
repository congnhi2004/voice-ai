# Completion Audit Refresh - 2026-05-10

Vai trò: Final Completion Audit Refresh Agent
Skill dùng: `voice-ai-qa-acceptance`
Repo: `/home/jhao/code/voice-ai`
Phạm vi ghi: chỉ file này và `docs/subagents/release-runtime-gate-20260510.md`. Không sửa code sản phẩm. Không dùng Exa. Context7 không áp dụng vì không sửa code/test. Không in hoặc ghi `OPENAI_API_KEY`; chỉ xác nhận `set/unset`.

## 1. Kết luận

**`public user-testable product prototype is now working for TTS + video localization`.** Public frontend đang load tại `http://103.27.237.252:4174/` với title `Voice AI Production Studio`. Public backend `/readyz` báo TTS provider `openai` ready và video localization `mode=auto`, `provider=openai`, ready. TTS OpenAI/marin trả WAV tải được và có MLflow run id. Video localization public real path trả `provider=openai`, `fallback=false`, transcript tiếng Anh, bản dịch/subtitle tiếng Việt, `voiceover.vi.wav`, `localized.vi.mp4`, và MLflow run id.

**`commercial production release still blocked by live GCP deploy/auth/billing/public observability/GitHub push`.** Chưa có live GCP/Cloud Run deployment evidence, auth vẫn `local-demo`, billing chưa production, storage runtime còn local filesystem, public MLflow qua IP vẫn bị host validation 403, và local `main` còn ahead `origin/main` 6 commits trong khi push HTTPS bị chặn do thiếu credential tương tác.

## 2. Prompt-to-artifact checklist

| Yêu cầu prompt | Artifact/bằng chứng | Kết luận |
| --- | --- | --- |
| Không sửa product code | Chỉ cập nhật `docs/subagents/completion-audit-20260510.md` và `docs/subagents/release-runtime-gate-20260510.md`. | Đạt. |
| Frontend public title/UI | `GET http://103.27.237.252:4174/` trả HTML có `<title>Voice AI Production Studio</title>`, description production studio, bundle `/assets/index-WkH4My9s.js`; report E2E có screenshot `docs/subagents/evidence/images/frontend-video-e2e-real-submit-fixed-20260510.png`. | Đạt. |
| `/readyz` TTS/video provider OpenAI | `/readyz`: `provider.name=openai`, `provider.ready=true`; `video_localization.mode=auto`, `provider=openai`, `ready=true`, `ffmpeg_available=true`. | Đạt. |
| `/v1/voices` gồm `marin`/`cedar` | `/v1/voices` trả `provider=openai` và danh sách có `marin`, `cedar`, cùng các voice OpenAI khác. | Đạt. |
| TTS synth OpenAI/marin | POST `/v1/synthesize` với `voice.name=marin`, `encoding=LINEAR16` trả `job_id=tts_783bbf4debe642128cfb6f3673a83a50`, `provider=openai`, `fallback=false`, `model=gpt-4o-mini-tts`. | Đạt. |
| Audio URL | `audio_url=http://103.27.237.252:8080/audio/tts_783bbf4debe642128cfb6f3673a83a50.wav`; `GET/HEAD` trả HTTP 200, `content-length=283244`, `content-type=audio/x-wav`. | Đạt. |
| MLflow run id | TTS response có `mlflow_run_id=41f318f86237449fafd7936ccc5669f9`, warnings rỗng. Video response có `mlflow_run_id=e18aed3732c74c9988307df0ad4da912`, warnings rỗng. | Đạt cho backend-to-MLflow tracking. |
| Video localization real API artifacts | POST `/v1/video-localization/jobs` với `/tmp/voice-ai-video-speech/source-speaking.mp4` trả `job_id=vid_abb2c7d6ed1a4dabae58ee1b3c98d3c7`, `provider=openai`, `fallback=false`, model `gpt-4o-mini-transcribe+gpt-4o-mini+gpt-4o-mini-tts`. Artifacts gồm `transcript.json`, `subtitles.vi.srt`, `subtitles.vi.vtt`, `voiceover.vi.wav`, `localized.vi.mp4`. | Đạt cho prototype public. |
| Video artifact probe | `ffprobe` trong container backend trên `localized.vi.mp4` báo streams `h264` video, `aac` audio, `mov_text` subtitle; duration `6.250000`, size `69757`. | Đạt. |
| Frontend video E2E report | `docs/subagents/frontend-video-e2e-fix-report-20260510.md`: public real submit HTTP 200, rendered transcript/SRT/VTT/audio/final MP4 links; local Playwright E2E `8 tests` passed with existing browser dependency workaround. | Đạt theo report mới nhất. |
| Tests summary | Backend reports mới nhất: `.venv/bin/pytest tests/backend/test_api.py` hoặc repo test pass `24 passed, 3 skipped, 2 warnings`. Frontend: lint passed, unit `4 passed`, build passed. Frontend video E2E: `8 tests` passed. | Đạt cho regression hiện tại. |
| Git ahead/push blocker | `git status --short --branch`: `## main...origin/main [ahead 6]`. `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD` fail: `could not read Username for 'https://github.com': terminal prompts disabled`. | Blocker release publication. |
| Cloud deploy blocker | `docs/subagents/cloud-production-lifecycle-report-20260510.md`: `gcloud`/credentials unavailable; no live Cloud Run revision, Artifact Registry image digest, GCS object, Secret Manager secret, GitHub Actions run, or rollback evidence. | Blocker commercial production. |

## 3. Coverage review

| Vùng kiểm chứng | Coverage hiện tại | Residual risk |
| --- | --- | --- |
| Public frontend | HTML/title public verified; frontend E2E report confirms video tab and real submit render artifact links. | Public service is Vite preview on `4174`, not live Cloud Run/CDN production. |
| Public TTS | Real OpenAI provider path verified directly through public API; WAV URL and MLflow run id present. | Audio content was not perceptually reviewed in this refresh; acceptance relies on OpenAI provider metadata and artifact availability. |
| Public video localization | Real upload verified directly through public API with speech MP4; OpenAI transcript/translation/TTS/mux path returned full artifacts. | Synchronous short-video endpoint only; long videos, background jobs, retries, cancellation, and storage lifecycle remain production gaps. |
| Observability | Backend-to-MLflow run ids present for current TTS and video requests. | Public MLflow API/UI by IP still returns HTTP 403 `Invalid Host header`; acceptable only if MLflow is intentionally internal-only and documented. |
| Privacy/secret handling | Runtime status reports `OPENAI_API_KEY: set` without value; this audit did not print or write the key. | Public artifacts include user-facing transcript/translation by product design; retention/access policy still needs production enforcement. |
| Automated tests | Latest reports cover backend, frontend lint/unit/build, and frontend video E2E. | Full CI was not executed live in a pushed GitHub branch because push/auth is blocked. |
| Deployment | Cloud lifecycle artifacts exist: workflow, deploy templates, runbook, secret map, lifecycle policy templates. | No live GCP deployment/auth/billing/public observability evidence. |

## 4. Commands run in this refresh

```bash
curl -fsS http://103.27.237.252:4174/
curl -fsS http://103.27.237.252:8080/readyz
curl -fsS http://103.27.237.252:8080/v1/voices
curl -fsS http://103.27.237.252:8080/v1/product/capabilities
taskset -c 0-3 ./scripts/local-services.sh status
curl -fsS -X POST http://103.27.237.252:8080/v1/synthesize -H 'Content-Type: application/json' --data-binary '{...}'
curl -fsSI http://103.27.237.252:8080/audio/tts_783bbf4debe642128cfb6f3673a83a50.wav
taskset -c 0-3 curl -fsS -X POST http://103.27.237.252:8080/v1/video-localization/jobs -F 'file=@/tmp/voice-ai-video-speech/source-speaking.mp4;type=video/mp4' -F source_language=en-US -F target_language=vi -F voice_name=marin
taskset -c 0-3 docker exec voice-ai-backend ffprobe -v error -show_entries format=duration,size:stream=codec_name,codec_type -of json /app/data/video-jobs/vid_abb2c7d6ed1a4dabae58ee1b3c98d3c7/localized.vi.mp4
curl -fsS http://103.27.237.252:8080/v1/video-localization/jobs/vid_abb2c7d6ed1a4dabae58ee1b3c98d3c7/artifacts/transcript.json
curl -sS -o /tmp/voice-ai-mlflow-server-info-current.txt -w 'HTTP %{http_code}\n' http://103.27.237.252:5000/api/3.0/mlflow/server-info
git status --short --branch
git log --oneline --decorate -8
GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD
```

## 5. Gaps còn lại

1. P0 commercial release: chưa deploy live lên GCP/Cloud Run; chưa có service URL Cloud Run, image digest promoted, GCS object proof, Secret Manager proof, Cloud Tasks proof, hoặc rollback proof.
2. P0 commercial release: auth vẫn `local-demo`, `production_identity=false`; chưa có identity, tenant, quota, abuse control, hoặc key lifecycle production.
3. P0 commercial release: billing `available=false`, `production_billing=false`; chưa thể release thương mại.
4. P1 production runtime: storage vẫn `mode=local`; artifact/audio path dưới `/app/data/...`, chưa chứng minh durable object storage/signed URL/retention enforcement.
5. P1 public observability: MLflow internal tracking hoạt động, nhưng public MLflow endpoint qua IP trả 403. Cần quyết định internal-only hoặc cấu hình access/proxy/auth an toàn.
6. P1 release hygiene: local `main` ahead `origin/main` 6 commits; tool push qua HTTPS bị chặn do thiếu GitHub credential không tương tác.
7. P2 docs hygiene: một số report/evidence cũ trong `docs/subagents/` còn ghi trạng thái local/demo trước fix. Hai file audit/gate này là quyết định mới nhất sau refresh.

## 6. Release decision

**User-testable public prototype:** PASS cho TTS và video localization. Người dùng có thể mở public frontend, dùng TTS OpenAI/marin, upload video tiếng Anh ngắn, nhận transcript, phụ đề tiếng Việt, audio lồng tiếng và MP4 localized.

**Commercial production release:** FAIL/BLOCKED. Chỉ được claim prototype public đang hoạt động; chưa được claim production thương mại cho đến khi live GCP deploy, auth, billing, durable storage, public/internal observability policy, CI/CD evidence, và GitHub push/release publication được đóng bằng bằng chứng runtime.
