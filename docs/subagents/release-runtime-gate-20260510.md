# Release Runtime Gate Refresh - 2026-05-10

Vai trò: Final Completion Audit Refresh Agent
Skill dùng: `voice-ai-qa-acceptance`
Repo: `/home/jhao/code/voice-ai`
Phạm vi: runtime/report-only. Không sửa code, config, service, hoặc secret. Không in `OPENAI_API_KEY`; chỉ báo set/unset.

## 1. Gate decision

**User testing gate: PASS.** `public user-testable product prototype is now working for TTS + video localization`.

**Commercial production gate: FAIL/BLOCKED.** `commercial production release still blocked by live GCP deploy/auth/billing/public observability/GitHub push`.

## 2. Runtime gate matrix

| Gate | Bằng chứng | Quyết định |
| --- | --- | --- |
| Public frontend | `http://103.27.237.252:4174/` HTTP 200; title `Voice AI Production Studio`; production workspace UI với TTS first-screen và video tab theo public HTML/report E2E. | Pass. |
| Public backend readiness | `/readyz` HTTP 200: `status=ready`, TTS `provider.name=openai`, provider ready; storage local ready; MLflow configured/ready; video `mode=auto`, `provider=openai`, FFmpeg available. | Pass cho prototype. |
| Runtime secret status | `./scripts/local-services.sh status`: `OPENAI_API_KEY: set`, OpenAI TTS/video model envs set, `GOOGLE_APPLICATION_CREDENTIALS: unset`, `PUBLIC_DEMO_PROFILE: set`, `REQUIRE_REAL_TTS: set`. No secret value printed. | Pass. |
| Voice catalog | `/v1/voices`: `provider=openai`; includes `marin` and `cedar`. | Pass. |
| TTS public smoke | POST `/v1/synthesize` with `voice.name=marin` returned `status=succeeded`, `provider=openai`, `fallback=false`, `model=gpt-4o-mini-tts`, `audio_url` returned. | Pass. |
| TTS artifact | `audio_url=http://103.27.237.252:8080/audio/tts_783bbf4debe642128cfb6f3673a83a50.wav`; HTTP 200, `content-length=283244`, `content-type=audio/x-wav`. | Pass. |
| TTS observability | TTS response: `mlflow_run_id=41f318f86237449fafd7936ccc5669f9`, warnings `[]`. | Pass internal tracking. |
| Video capabilities | `/v1/product/capabilities`: `active_provider=openai`; video localization `available=true`, `demo_mode=false`, artifacts include transcript/SRT/VTT/voiceover/localized video; auth still `local-demo`; billing unavailable. | Pass for prototype video, fail for commercial product. |
| Video public real path | POST speech MP4 to `/v1/video-localization/jobs`: `job_id=vid_abb2c7d6ed1a4dabae58ee1b3c98d3c7`, `provider=openai`, `fallback=false`, model `gpt-4o-mini-transcribe+gpt-4o-mini+gpt-4o-mini-tts`, latency `6733ms`. | Pass. |
| Video artifacts | Response returned `transcript.json`, `subtitles.vi.srt`, `subtitles.vi.vtt`, `voiceover.vi.wav` `362444` bytes, `localized.vi.mp4` `69757` bytes. Transcript translated: `Xin chào, đây là một video ngắn bằng tiếng Anh...`. | Pass. |
| Video mux probe | `ffprobe` on final MP4: h264 video, aac audio, mov_text subtitle; duration `6.250000`; size `69757`. | Pass. |
| Frontend video E2E | `frontend-video-e2e-fix-report-20260510.md`: public real upload HTTP 200 rendered transcript/SRT/VTT/audio/final MP4 links; local Playwright E2E passed `8 tests`. | Pass by latest report. |
| Automated tests | Backend latest reports: `24 passed, 3 skipped, 2 warnings`; frontend lint passed, unit `4 passed`, build passed; video E2E `8 tests` passed with browser dependency workaround. | Pass for prototype regression. |
| Public MLflow endpoint | `http://103.27.237.252:5000/api/3.0/mlflow/server-info` returns HTTP 403 `Invalid Host header - possible DNS rebinding attack detected`. | Fail if public observability is required; acceptable only as internal-only with docs. |
| Cloud production deploy | Cloud lifecycle docs/templates exist, but live deploy was not attempted because `gcloud`/GCP credentials were unavailable; no Cloud Run/GCS/Secret Manager/GitHub Actions live proof. | Block commercial release. |
| Git publication | `## main...origin/main [ahead 6]`; `GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD` fails due missing HTTPS username/token prompt. | Block release publication from tool session. |

## 3. Current public artifact summary

TTS response summary:

```text
job_id=tts_783bbf4debe642128cfb6f3673a83a50
provider=openai
fallback=false
model=gpt-4o-mini-tts
voice=marin
audio_url=http://103.27.237.252:8080/audio/tts_783bbf4debe642128cfb6f3673a83a50.wav
audio.bytes=283244
content_type=audio/wav
mlflow_run_id=41f318f86237449fafd7936ccc5669f9
warnings=[]
```

Video response summary:

```text
job_id=vid_abb2c7d6ed1a4dabae58ee1b3c98d3c7
provider=openai
fallback=false
model=gpt-4o-mini-transcribe+gpt-4o-mini+gpt-4o-mini-tts
source_language=en-US
target_language=vi
transcript_chars=95
translated_chars=117
voiceover.vi.wav bytes=362444
localized.vi.mp4 bytes=69757
mlflow_run_id=e18aed3732c74c9988307df0ad4da912
warnings=[]
```

Final video probe:

```text
streams: h264 video, aac audio, mov_text subtitle
duration=6.250000
size=69757
```

## 4. Coverage review

This gate covers the currently public, user-testable prototype surfaces: frontend load, backend readiness, voices, TTS synth, audio artifact serving, video upload, OpenAI transcript/translation/TTS/mux path, artifact URLs, MLflow run id presence, test summaries, runtime status, git status, push blocker, and cloud deploy blocker.

This gate does not certify commercial production. It does not prove live Cloud Run, Artifact Registry, GCS persistence, Secret Manager wiring, Cloud Tasks processing, production identity, production billing, alerting dashboards, public MLflow access, or GitHub release publication.

## 5. Remaining gaps before commercial release

1. Live GCP deploy: run and capture Cloud Run service/revision URL, image digest, Secret Manager mapping, GCS artifact proof, Cloud Tasks/job proof, and rollback evidence.
2. Auth: replace or hard-gate `local-demo` identity before external commercial users.
3. Billing: implement production billing/entitlements; current `/v1/product/capabilities` says billing unavailable.
4. Storage: replace local `/app/data/...` artifact serving with durable object storage, signed URL/access control, retention, and cleanup evidence.
5. Observability: decide MLflow internal-only vs public; current public IP API returns 403 host validation.
6. Release publication: configure secure GitHub auth and push the 6 ahead commits without writing tokens to repo/chat/logs.
7. CI/CD: capture GitHub Actions run evidence after push; current tests are report/local command evidence, not a pushed CI green run.

## 6. Final gate outcome

**Allow controlled public user testing:** yes, for TTS + video localization prototype at the public URLs.

**Allow commercial production release:** no. The runtime is now good enough to test the product experience publicly, but production release remains blocked by deploy, auth, billing, observability, storage, and Git publication gates.
