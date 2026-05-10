# Skill Author B Report

## Scope

Created four reusable Codex skills under `/home/jhao/.codex/skills`:

- `voice-ai-backend-builder`
- `voice-ai-frontend-builder`
- `voice-ai-infra-observability`
- `voice-ai-qa-acceptance`

No product code was modified.

## Files Created

- `/home/jhao/.codex/skills/voice-ai-backend-builder/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-backend-builder/agents/openai.yaml`
- `/home/jhao/.codex/skills/voice-ai-frontend-builder/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-frontend-builder/agents/openai.yaml`
- `/home/jhao/.codex/skills/voice-ai-infra-observability/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-infra-observability/agents/openai.yaml`
- `/home/jhao/.codex/skills/voice-ai-qa-acceptance/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-qa-acceptance/agents/openai.yaml`
- `/home/jhao/code/voice-ai/docs/subagents/skill-author-b-report.md`

## Tooling Used

- Read `/home/jhao/.codex/skills/.system/skill-creator/SKILL.md`.
- Read `/home/jhao/.codex/skills/.system/skill-creator/references/openai_yaml.md`.
- Created skill scaffolds with `/home/jhao/.codex/skills/.system/skill-creator/scripts/init_skill.py`.
- Regenerated `agents/openai.yaml` with `/home/jhao/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py`.
- Validated each skill with `/home/jhao/.codex/skills/.system/skill-creator/scripts/quick_validate.py`.

## Validation Summary

Command outputs:

- `voice-ai-backend-builder`: `Skill is valid!`
- `voice-ai-frontend-builder`: `Skill is valid!`
- `voice-ai-infra-observability`: `Skill is valid!`
- `voice-ai-qa-acceptance`: `Skill is valid!`

Note: this environment has `python3`, not `python`, so the official scripts were run with `python3`.

## Invocation

- Backend implementation: `Use $voice-ai-backend-builder to implement the production TTS API and verify backend behavior.`
- Frontend implementation: `Use $voice-ai-frontend-builder to implement the TTS UI and verify it visually.`
- Infra and observability: `Use $voice-ai-infra-observability to prepare deployment, observability, and operational docs.`
- QA acceptance: `Use $voice-ai-qa-acceptance to run acceptance checks and write evidence for the TTS app.`

## Notes

- The frontend skill explicitly requires current web/UI research before design or implementation.
- No extra resource directories were added; each skill contains only `SKILL.md` and `agents/openai.yaml`.

## Addendum: Video Localization Scope Update

Updated the four existing skills to cover the expanded project scope: input video in Chinese or English, Vietnamese script/subtitles on the video, Vietnamese dubbed audio, and final localized video output.

Changed files:

- `/home/jhao/.codex/skills/voice-ai-backend-builder/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-backend-builder/agents/openai.yaml`
- `/home/jhao/.codex/skills/voice-ai-frontend-builder/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-frontend-builder/agents/openai.yaml`
- `/home/jhao/.codex/skills/voice-ai-infra-observability/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-infra-observability/agents/openai.yaml`
- `/home/jhao/.codex/skills/voice-ai-qa-acceptance/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-qa-acceptance/agents/openai.yaml`
- `/home/jhao/code/voice-ai/docs/subagents/skill-author-b-report.md`

Research basis from official docs:

- Google Speech-to-Text supports asynchronous long-running recognition for long audio and requires GCS for long local-file audio inputs: https://cloud.google.com/speech-to-text/docs/async-recognize
- Google Cloud Translation supports translating text and using target language codes, including Vietnamese via `vi`: https://docs.cloud.google.com/translate/docs/translate-text
- Google Cloud Text-to-Speech `text:synthesize` returns `audioContent` bytes for synthesized audio: https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
- FFmpeg official documentation covers video, audio, subtitle, muxing, and related media processing: https://ffmpeg.org/ffmpeg-doc.html

Validation output after edits:

- `voice-ai-backend-builder`: `Skill is valid!`
- `voice-ai-frontend-builder`: `Skill is valid!`
- `voice-ai-infra-observability`: `Skill is valid!`
- `voice-ai-qa-acceptance`: `Skill is valid!`

## Addendum: Context7 Requirement Update

Updated the code-writing project skills to require Context7 via MCP Docker before implementing or modifying code that depends on a library/framework. Also updated `voice-ai-techlead-reviewer` because it was safe to edit.

Changed files:

- `/home/jhao/.codex/skills/voice-ai-backend-builder/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-frontend-builder/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-infra-observability/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-qa-acceptance/SKILL.md`
- `/home/jhao/.codex/skills/voice-ai-techlead-reviewer/SKILL.md`
- `/home/jhao/code/voice-ai/docs/subagents/skill-author-b-report.md`

Rule added:

- Before code changes involving libraries/frameworks, resolve the library with `mcp__MCP_DOCKER__resolve_library_id` and fetch docs with `mcp__MCP_DOCKER__get_library_docs` for the relevant topic/version.
- Prefer official/current docs via web search for cloud/service/platform facts, and Context7 for library API usage.
- Reports must list Context7 library IDs/topics used, or explicitly state why Context7 was not applicable/unavailable.
- Do not use stale memory for library APIs when Context7 is available.

Validation output after edits:

- `voice-ai-backend-builder`: `Skill is valid!`
- `voice-ai-frontend-builder`: `Skill is valid!`
- `voice-ai-infra-observability`: `Skill is valid!`
- `voice-ai-qa-acceptance`: `Skill is valid!`
- `voice-ai-techlead-reviewer`: `Skill is valid!`
