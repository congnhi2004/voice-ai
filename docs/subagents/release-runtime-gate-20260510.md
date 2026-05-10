# Release Runtime Gate - 2026-05-10

Vai trò: Final Acceptance Audit Agent
Skill dùng: `voice-ai-qa-acceptance`
Repo: `/home/jhao/code/voice-ai`
Phạm vi: gate runtime/report-only. Không sửa code, config, service, hoặc secret. Không in `OPENAI_API_KEY`; chỉ báo set/unset.

## 1. Release decision

**Cho phép user testing có kiểm soát cho public TTS demo.** Public frontend và backend đang sống; runtime guard đã nạp `.env.runtime`; public `/readyz` báo OpenAI ready; `/v1/voices` có `marin`/`cedar`; `/v1/synthesize` với `marin` trả WAV tải được và có MLflow run id.

**Chặn production/commercial release.** Sản phẩm đầy đủ vẫn chưa production-ready vì video localization còn local deterministic demo, storage còn local filesystem, auth/billing còn demo, public MLflow qua IP bị 403, và chưa có bằng chứng live cho Cloud Run/GCS/Cloud Tasks/CI-CD production.

## 2. Runtime gate evidence

| Gate | Bằng chứng | Quyết định |
| --- | --- | --- |
| Frontend public | `http://103.27.237.252:4174/` HTTP 200; title `Voice AI Text to Real Voice Studio`. | Pass. |
| Backend public | `http://103.27.237.252:8080/healthz` HTTP 200, service `voice-ai`, version `0.1.0`. | Pass. |
| Runtime env/guard | `./scripts/local-services.sh status`: `runtime env file: loaded`, `PUBLIC_DEMO_PROFILE: set`, `REQUIRE_REAL_TTS: set`. | Pass. |
| Secret handling | Status báo `backend OPENAI_API_KEY: set`, không in value. | Pass trong audit. |
| Backend image/container | `backend image: voice-ai:durable-20260510`; `voice-ai-backend` up/healthy; `voice-ai-mlflow` up. | Pass. |
| OpenAI readiness | `/readyz`: provider `openai`, ready `true`; MLflow configured/ready; video localization `mode=local`, ffmpeg available. | Pass cho TTS; video vẫn demo. |
| Voice catalog | `/v1/voices`: provider `openai`; includes `marin`, `cedar`, `coral`, và các OpenAI voices khác. | Pass. |
| TTS smoke | `POST /v1/synthesize` với `voice.name=marin` trả `provider.name=openai`, `fallback=false`, model `gpt-4o-mini-tts`, status `succeeded`. | Pass. |
| Audio artifact | WAV URL tải được; file 295,244 bytes; RIFF/WAVE PCM mono 24 kHz; container `ffprobe` duration 6.15s. | Pass. |
| MLflow run | Response có `mlflow_run_id=67fafe230e4e4dadb31222777e67e235`, warnings `[]`; MLflow logs có create/log/get/update HTTP 200. | Pass nội bộ. |
| Public MLflow | `http://103.27.237.252:5000/api/3.0/mlflow/server-info` trả HTTP 403 `Invalid Host header`. | Fail nếu gate yêu cầu public observability endpoint. |
| Product mode | `/v1/product/capabilities`: environment `local`, mode `demo`, active_provider `openai`, `local_fallback=true`; video `demo_mode=true`; auth `local-demo`; billing unavailable. | Fail cho production/commercial. |
| Tests | Backend `21 passed, 3 skipped`; frontend lint pass, Vitest `4 passed`, Vite build pass. | Pass cho regression hiện tại. |
| Git publish | `main...origin/main [ahead 3]`; push dry-run qua HTTPS fail vì thiếu username/token prompt. | Fail cho release publication từ tool session. |

## 3. Current public TTS acceptance

Request đã chạy:

```json
{
  "text": "Xin chao, day la kiem tra nghiem thu OpenAI marin cho Voice AI.",
  "voice": {"language_code": "vi-VN", "name": "marin"},
  "audio": {"encoding": "LINEAR16"},
  "metadata": {"client_reference_id": "final-acceptance-openai-marin-20260510"}
}
```

Response chính:

```text
job_id=tts_c945f6990f6049d2a9f404df3fb831e2
provider=openai
fallback=false
model=gpt-4o-mini-tts
voice=marin
audio_url=http://103.27.237.252:8080/audio/tts_c945f6990f6049d2a9f404df3fb831e2.wav
audio.bytes=295244
content_type=audio/wav
mlflow_run_id=67fafe230e4e4dadb31222777e67e235
warnings=[]
```

Audio check:

```text
/tmp/voice-ai-openai-marin.wav: RIFF/WAVE audio, Microsoft PCM, 16 bit, mono 24000 Hz
ffprobe in backend container: codec pcm_s16le, audio, sample_rate 24000, channels 1, duration 6.150000
```

## 4. Evidence artifacts

Ảnh evidence hiện có dưới `docs/subagents/evidence/images/`:

```text
docs/subagents/evidence/images/pm-openai-web-smoke-20260510.png
docs/subagents/evidence/images/pm-redesign-desktop-20260510.png
docs/subagents/evidence/images/pm-redesign-mobile-20260510.png
docs/subagents/evidence/images/pm-redesign-tts-success-20260510.png
docs/subagents/evidence/images/qa-public-desktop-20260510.png
docs/subagents/evidence/images/qa-public-mobile-20260510.png
docs/subagents/evidence/images/final-gate-public-desktop-20260510.png
docs/subagents/evidence/images/final-gate-public-mobile-20260510.png
```

API evidence hiện có dưới `docs/subagents/evidence/api/` vẫn bao gồm các final-gate files trước fix; một số file đó phản ánh trạng thái cũ local provider. Với release decision hiện tại, ưu tiên bằng chứng runtime mới trong report này.

## 5. Git gate

Current branch:

```text
## main...origin/main [ahead 3]
```

Ahead commits:

```text
fdaafad Organize subagent reports and evidence
f6e3f9c Mount MLflow artifacts in local runtime
2bbde31 Pass TTS runtime env through local services
```

Remote:

```text
origin https://github.com/congnhi2004/voice-ai.git
```

Push blocker:

```text
GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Kết luận: tool session chưa có HTTPS credential để push. Không ghi token vào repo, docs, shell history, hoặc chat.

## 6. Production/commercial blockers

1. Video localization chưa production: public capabilities vẫn báo `demo_mode=true`; evidence hiện có dùng local deterministic transcript/translation/dub artifacts, không phải STT + translation + dubbing thật.
2. Storage chưa production: readiness storage `mode=local`; audio path nằm dưới `/app/data/audio`; chưa có GCS/object storage/signed URL proof.
3. Auth/billing chưa production: auth mode `local-demo`, billing unavailable.
4. Observability public chưa chốt: MLflow nội bộ ghi run tốt, nhưng public API qua IP 403. Cần quyết định internal-only hoặc cấu hình public access an toàn.
5. CI/CD/deploy chưa chứng minh live production: chưa có GitHub Actions run, Cloud Run revision, image digest promotion, GCS artifact proof, Cloud Tasks job proof, rollback evidence.
6. Release publication chưa xong: branch ahead origin 3 commits và push bị chặn bởi HTTPS credential.

## 7. Gate outcome

**User testing gate:** Pass cho luồng public TTS demo OpenAI/marin, với điều kiện nói rõ đây là TTS demo/user testing, không phải toàn bộ production product.

**Production/commercial gate:** Fail. Không release thương mại và không claim full production complete cho đến khi các blocker ở mục 6 được xử lý và có bằng chứng public/runtime tương ứng.
