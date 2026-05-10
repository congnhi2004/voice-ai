import {
  ApiError,
  ReadinessResponse,
  SynthesizeResponse,
  VideoLocalizationArtifact,
  VideoLocalizationJob,
  VideoLocalizationSegment,
  Voice,
  VoiceAiClient,
  normalizeBaseUrl,
  resolveArtifactUrl,
  resolveAudioUrl
} from "./api";
import "./styles.css";

const storageKeys = {
  baseUrl: "voice-ai.base-url",
  history: "voice-ai.history",
  videoHistory: "voice-ai.video-history",
  demoUser: "voice-ai.demo-user"
};

function isLoopbackHost(hostname: string) {
  return ["localhost", "127.0.0.1", "::1", "[::1]"].includes(hostname);
}

function isLocalApiUrl(value: string) {
  try {
    return isLoopbackHost(new URL(value).hostname);
  } catch {
    return false;
  }
}

function deriveDefaultBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured) {
    return normalizeBaseUrl(configured);
  }

  if (typeof window === "undefined") {
    return "http://localhost:8080";
  }

  const { hostname, protocol } = window.location;
  if (isLoopbackHost(hostname)) {
    return "http://localhost:8080";
  }

  return normalizeBaseUrl(`${protocol === "https:" ? "https" : "http"}://${hostname}:8080`);
}

const defaultBaseUrl = deriveDefaultBaseUrl();

function initialBaseUrl() {
  const stored = localStorage.getItem(storageKeys.baseUrl);
  if (!stored) {
    return defaultBaseUrl;
  }

  const publicFrontend = typeof window !== "undefined" && !isLoopbackHost(window.location.hostname);
  if (publicFrontend && isLocalApiUrl(stored)) {
    return defaultBaseUrl;
  }

  return normalizeBaseUrl(stored);
}

type Workflow = "video" | "tts";
type AuthMode = "login" | "register";

type HistoryItem = {
  jobId: string;
  status: string;
  textPreview: string;
  voice: string;
  language: string;
  encoding: string;
  audioUrl: string;
  latencyMs?: number;
  durationMs?: number;
  provider?: string;
  createdAt: string;
};

type VideoHistoryItem = {
  jobId: string;
  status: string;
  sourceLanguage: string;
  targetVoice: string;
  fileName: string;
  audioUrl: string;
  transcriptUrl: string;
  videoUrl: string;
  srtUrl: string;
  createdAt: string;
};

type AppState = {
  activeWorkflow: Workflow;
  authMode: AuthMode;
  showAuthPanel: boolean;
  demoUser: string;
  baseUrl: string;
  apiKey: string;
  voices: Voice[];
  readiness: ReadinessResponse | null;
  voiceLoading: boolean;
  synthLoading: boolean;
  selectedVoiceName: string;
  selectedLanguage: string;
  encoding: string;
  mode: "text" | "ssml";
  text: string;
  speakingRate: number;
  pitch: number;
  volumeGainDb: number;
  clientReferenceId: string;
  latest: SynthesizeResponse | null;
  latestAudioUrl: string;
  error: string;
  history: HistoryItem[];
  videoFile: File | null;
  videoSourceLanguage: "zh" | "zh-CN" | "en" | "en-US";
  videoTargetVoiceName: string;
  videoBurnSubtitles: boolean;
  videoClientReferenceId: string;
  videoLoading: boolean;
  videoJob: VideoLocalizationJob | null;
  videoError: string;
  videoScript: string;
  videoSrt: string;
  videoHistory: VideoHistoryItem[];
};

const fallbackVoices: Voice[] = [
  {
    name: "en-US-Standard-C",
    language_codes: ["en-US"],
    ssml_gender: "FEMALE",
    natural_sample_rate_hz: 24000,
    supported_encodings: ["MP3", "LINEAR16", "OGG_OPUS"]
  },
  {
    name: "en-US-Standard-D",
    language_codes: ["en-US"],
    ssml_gender: "MALE",
    natural_sample_rate_hz: 24000,
    supported_encodings: ["MP3", "LINEAR16", "OGG_OPUS"]
  },
  {
    name: "vi-VN-Standard-A",
    language_codes: ["vi-VN"],
    ssml_gender: "FEMALE",
    natural_sample_rate_hz: 24000,
    supported_encodings: ["MP3", "LINEAR16"]
  }
];

const videoUploadLimitBytes = 250 * 1024 * 1024;
const acceptedVideoExtensions = [".mp4", ".mov", ".webm", ".m4v"];

const state: AppState = {
  activeWorkflow: "tts",
  authMode: "register",
  showAuthPanel: false,
  demoUser: localStorage.getItem(storageKeys.demoUser) || "",
  baseUrl: initialBaseUrl(),
  apiKey: "",
  voices: fallbackVoices,
  readiness: null,
  voiceLoading: false,
  synthLoading: false,
  selectedVoiceName: fallbackVoices[0].name,
  selectedLanguage: fallbackVoices[0].language_codes[0],
  encoding: "MP3",
  mode: "text",
  text: "Xin chao, day la ban nghe thu cua Voice AI. Hay dan kich ban ngan vao day, chon giong doc, dieu chinh toc do, roi tao tep am thanh co the nghe va tai ve ngay.",
  speakingRate: 1,
  pitch: 0,
  volumeGainDb: 0,
  clientReferenceId: "",
  latest: null,
  latestAudioUrl: "",
  error: "",
  history: readJson<HistoryItem[]>(storageKeys.history, []),
  videoFile: null,
  videoSourceLanguage: "en-US",
  videoTargetVoiceName: "vi-VN-Standard-A",
  videoBurnSubtitles: true,
  videoClientReferenceId: "",
  videoLoading: false,
  videoJob: null,
  videoError: "",
  videoScript: "",
  videoSrt: "",
  videoHistory: readJson<VideoHistoryItem[]>(storageKeys.videoHistory, [])
};

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("Missing #app root");
}
const root = app;

const getClient = () => new VoiceAiClient({ baseUrl: state.baseUrl, apiKey: state.apiKey });

function readJson<T>(key: string, fallback: T) {
  try {
    return JSON.parse(localStorage.getItem(key) || "") as T;
  } catch {
    return fallback;
  }
}

function saveSettings() {
  localStorage.setItem(storageKeys.baseUrl, state.baseUrl);
}

function saveHistory() {
  localStorage.setItem(storageKeys.history, JSON.stringify(state.history.slice(0, 12)));
}

function saveVideoHistory() {
  localStorage.setItem(storageKeys.videoHistory, JSON.stringify(state.videoHistory.slice(0, 12)));
}

function selectedVoice() {
  return state.voices.find((voice) => voice.name === state.selectedVoiceName) || state.voices[0] || fallbackVoices[0];
}

function vietnameseVoices() {
  const voices = state.voices.filter((voice) => voice.language_codes.some((language) => language.toLowerCase().startsWith("vi")));
  return voices.length ? voices : fallbackVoices.filter((voice) => voice.language_codes.some((language) => language.toLowerCase().startsWith("vi")));
}

function selectedVideoVoice() {
  return vietnameseVoices().find((voice) => voice.name === state.videoTargetVoiceName) || vietnameseVoices()[0] || fallbackVoices[2];
}

function selectedVoiceEncodings() {
  return selectedVoice().supported_encodings?.length ? selectedVoice().supported_encodings! : ["MP3", "LINEAR16", "OGG_OPUS"];
}

function voiceLabel(voice: Voice) {
  const language = voice.language_codes.join(", ");
  const gender = voice.ssml_gender ? `, ${voice.ssml_gender.toLowerCase()}` : "";
  return `${voice.name} (${language}${gender})`;
}

function formatNumber(value?: number, suffix = "") {
  return typeof value === "number" ? `${value.toLocaleString()}${suffix}` : "Not reported";
}

function formatError(error: unknown) {
  if (error instanceof ApiError) {
    const details = [error.code, error.status ? `HTTP ${error.status}` : "", error.requestId ? `request ${error.requestId}` : ""]
      .filter(Boolean)
      .join(" - ");
    return details ? `${error.message} (${details})` : error.message;
  }
  return error instanceof Error ? error.message : "Unexpected error";
}

function validateVideoFile(file: File | null) {
  if (!file) {
    return "Upload a Chinese or English video before starting localization. Use the quick TTS tab if you only want a no-file audio test.";
  }

  const name = file.name.toLowerCase();
  const hasAcceptedExtension = acceptedVideoExtensions.some((extension) => name.endsWith(extension));
  const hasAcceptedMime = file.type === "" || file.type.startsWith("video/");

  if (!hasAcceptedMime || !hasAcceptedExtension) {
    return "Select an MP4, MOV, M4V, or WebM video. Browser hints are not security validation; the backend will still verify the upload.";
  }

  if (file.size <= 0) {
    return "The selected video is empty. Choose a source file with audio to localize.";
  }

  if (file.size > videoUploadLimitBytes) {
    return "The selected video is larger than the 250 MB MVP upload limit.";
  }

  return "";
}

async function refreshStatus() {
  state.voiceLoading = true;
  state.error = "";
  state.videoError = "";
  render();

  try {
    const client = getClient();
    const [readiness, voiceResponse] = await Promise.allSettled([client.readiness(), client.voices()]);

    if (readiness.status === "fulfilled") {
      state.readiness = readiness.value;
    }

    if (voiceResponse.status === "fulfilled" && voiceResponse.value.voices.length) {
      state.voices = voiceResponse.value.voices;
      if (!state.voices.some((voice) => voice.name === state.selectedVoiceName)) {
        state.selectedVoiceName = state.voices[0].name;
        state.selectedLanguage = state.voices[0].language_codes[0];
      }
      if (!vietnameseVoices().some((voice) => voice.name === state.videoTargetVoiceName)) {
        state.videoTargetVoiceName = vietnameseVoices()[0]?.name || fallbackVoices[2].name;
      }
    }

    const rejected = [readiness, voiceResponse].find((result) => result.status === "rejected");
    if (rejected?.status === "rejected") {
      const message = `${formatError(rejected.reason)} Fallback voices remain available for prototype testing.`;
      state.error = message;
      state.videoError = message;
    }
  } finally {
    state.voiceLoading = false;
    render();
  }
}

async function synthesize() {
  const content = state.text.trim();
  if (!content) {
    state.error = "Enter text or SSML before synthesizing.";
    render();
    return;
  }

  if (content.length > 5000) {
    state.error = "Input exceeds the MVP limit of 5,000 characters.";
    render();
    return;
  }

  const voice = selectedVoice();
  const languageCode = state.selectedLanguage || voice.language_codes[0];
  state.synthLoading = true;
  state.error = "";
  render();

  try {
    const response = await getClient().synthesize(
      {
        text: state.mode === "text" ? content : null,
        ssml: state.mode === "ssml" ? content : null,
        voice: {
          language_code: languageCode,
          name: voice.name,
          ssml_gender: voice.ssml_gender
        },
        audio: {
          encoding: state.encoding,
          speaking_rate: state.speakingRate,
          pitch: state.pitch,
          volume_gain_db: state.volumeGainDb,
          sample_rate_hz: voice.natural_sample_rate_hz
        },
        metadata: {
          client_reference_id: state.clientReferenceId.trim() || undefined
        }
      },
      state.clientReferenceId.trim() || undefined
    );

    const audioUrl = resolveAudioUrl(state.baseUrl, response.audio_url, response.audio_path);
    state.latest = response;
    state.latestAudioUrl = audioUrl;
    state.history = [
      {
        jobId: response.job_id,
        status: response.status,
        textPreview: content.slice(0, 120),
        voice: voice.name,
        language: languageCode,
        encoding: state.encoding,
        audioUrl,
        latencyMs: response.latency_ms,
        durationMs: response.duration_ms,
        provider: response.provider?.name,
        createdAt: new Date().toISOString()
      },
      ...state.history
    ].slice(0, 12);
    saveHistory();
  } catch (error) {
    state.error = formatError(error);
  } finally {
    state.synthLoading = false;
    render();
  }
}

async function startVideoLocalization() {
  const validationError = validateVideoFile(state.videoFile);
  if (validationError) {
    state.videoError = validationError;
    render();
    return;
  }

  const voice = selectedVideoVoice();
  state.videoLoading = true;
  state.videoError = "";
  state.videoJob = {
    job_id: "local_preview",
    status: "processing",
    progress: 12,
    stage: "Uploading source video"
  };
  render();

  try {
    const response = await getClient().startVideoLocalization(
      {
        video: state.videoFile!,
        source_language: state.videoSourceLanguage,
        target_language: "vi",
        target_voice_name: voice.name,
        target_voice_language_code: voice.language_codes[0],
        generate_subtitles: true,
        burn_subtitles: state.videoBurnSubtitles,
        metadata: {
          client_reference_id: state.videoClientReferenceId.trim() || undefined
        }
      },
      state.videoClientReferenceId.trim() || undefined
    );

    applyVideoJob(response);
    if (!isFinalVideoStatus(response.status)) {
      window.setTimeout(() => void pollVideoJob(response.job_id), 1200);
    }
  } catch (error) {
    state.videoError = formatError(error);
    state.videoJob = null;
  } finally {
    state.videoLoading = false;
    render();
  }
}

async function pollVideoJob(jobId: string) {
  try {
    const response = await getClient().videoLocalizationJob(jobId);
    applyVideoJob(response);
    render();
    if (!isFinalVideoStatus(response.status)) {
      window.setTimeout(() => void pollVideoJob(jobId), 2500);
    }
  } catch (error) {
    state.videoError = formatError(error);
    render();
  }
}

function isFinalVideoStatus(status: string) {
  return ["succeeded", "failed", "needs_review", "canceled"].includes(status);
}

function formatTimestampFromMs(value?: number) {
  const ms = Math.max(0, value ?? 0);
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  const seconds = Math.floor((ms % 60_000) / 1000);
  const millis = Math.floor(ms % 1000);
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds
    .toString()
    .padStart(2, "0")},${millis.toString().padStart(3, "0")}`;
}

function segmentText(segment: VideoLocalizationSegment) {
  return segment.vietnamese_text || segment.translated_text || segment.text || "";
}

function videoScriptPreview(job: VideoLocalizationJob) {
  if (job.script?.vietnamese_text) {
    return job.script.vietnamese_text;
  }

  const translatedSegments = job.segments?.map(segmentText).filter(Boolean) || [];
  return translatedSegments.join("\n\n");
}

function videoSrtPreview(job: VideoLocalizationJob) {
  if (job.script?.srt) {
    return job.script.srt;
  }

  const segments = job.segments?.filter((segment) => segmentText(segment)) || [];
  if (!segments.length) {
    return "";
  }

  return segments
    .map((segment, index) => {
      const start = segment.start || formatTimestampFromMs(segment.start_ms);
      const end = segment.end || formatTimestampFromMs(segment.end_ms ?? (segment.start_ms ?? 0) + 2500);
      return `${segment.index ?? index + 1}\n${start} --> ${end}\n${segmentText(segment)}`;
    })
    .join("\n\n");
}

function applyVideoJob(job: VideoLocalizationJob) {
  state.videoJob = job;
  const scriptPreview = videoScriptPreview(job);
  const srtPreview = videoSrtPreview(job);
  state.videoScript = scriptPreview || state.videoScript;
  state.videoSrt = srtPreview || state.videoSrt;

  if (job.job_id && isFinalVideoStatus(job.status)) {
    const artifacts = videoArtifactUrls(job);
    state.videoHistory = [
      {
        jobId: job.job_id,
        status: job.status,
        sourceLanguage: state.videoSourceLanguage,
        targetVoice: selectedVideoVoice().name,
        fileName: job.input_filename || state.videoFile?.name || "Uploaded video",
        audioUrl: artifacts.audio,
        transcriptUrl: artifacts.transcript,
        videoUrl: artifacts.video,
        srtUrl: artifacts.srt,
        createdAt: new Date().toISOString()
      },
      ...state.videoHistory.filter((item) => item.jobId !== job.job_id)
    ].slice(0, 12);
    saveVideoHistory();
  }
}

function artifactKind(value: VideoLocalizationArtifact | string) {
  if (typeof value === "string") {
    return value.toLowerCase();
  }
  return [value.kind, value.type, value.name, value.format, value.filename, value.path, value.download_url, value.url].filter(Boolean).join(" ").toLowerCase();
}

function artifactHref(value: VideoLocalizationArtifact | string, jobId: string) {
  if (typeof value === "string") {
    return `${normalizeBaseUrl(state.baseUrl)}/v1/video-localization/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(value)}`;
  }
  return resolveArtifactUrl(state.baseUrl, value.download_url || value.url, value.path || value.filename);
}

function findArtifactUrl(job: VideoLocalizationJob | null | undefined, candidates: string[], route = "artifacts") {
  const artifacts = job?.artifacts;
  if (!artifacts) {
    return "";
  }

  if (Array.isArray(artifacts)) {
    const match = candidates
      .map((candidate) => artifacts.find((artifact) => artifactKind(artifact).includes(candidate)))
      .find(Boolean);
    return match ? artifactHref(match, job?.job_id || "") : "";
  }

  const keyedArtifacts = artifacts as Extract<VideoLocalizationJob["artifacts"], Record<string, string | undefined>>;
  const urlKey = `${candidates[0]}_url` as keyof typeof keyedArtifacts;
  const pathKey = `${candidates[0]}_path` as keyof typeof keyedArtifacts;
  return resolveArtifactUrl(state.baseUrl, keyedArtifacts[urlKey], keyedArtifacts[pathKey], route);
}

function videoArtifactUrls(job = state.videoJob) {
  return {
    transcript: findArtifactUrl(job, ["transcript", "vietnamese_transcript"]),
    srt: findArtifactUrl(job, ["srt", "subtitles_srt"]),
    vtt: findArtifactUrl(job, ["vtt", "subtitles_vtt"]),
    audio: findArtifactUrl(job, ["voiceover_audio", "vietnamese_audio", "dubbed_audio", "localized_audio", "audio"], "audio"),
    video: findArtifactUrl(job, ["localized_video", "final_video", "mp4"])
  };
}

function switchWorkflow(workflow: Workflow, options: { scroll?: boolean; focusUpload?: boolean } = {}) {
  state.activeWorkflow = workflow;
  render();

  window.requestAnimationFrame(() => {
    if (options.scroll) {
      document.querySelector("#studio")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (workflow === "video" && options.focusUpload) {
      document.querySelector<HTMLInputElement>("#video-file")?.focus();
    }
  });
}

function render() {
  const readinessLabel = state.readiness?.status || "demo";
  const provider = state.readiness?.provider;

  root.innerHTML = `
    <a class="skip-link" href="#studio">Skip to prototype studio</a>
    <header class="top-nav">
      <a class="brand" href="#prototype" aria-label="Voice AI home">
        <span class="brand-mark" aria-hidden="true">VA</span>
        <span>Voice AI</span>
      </a>
      <nav class="nav-links" aria-label="Primary">
        <a href="#product">Product</a>
        <a href="#workflow">Workflow</a>
        <a href="#pricing">Pricing</a>
        <a href="#security">Security</a>
        <a href="#docs">Docs</a>
      </nav>
      <div class="nav-actions">
        <button class="ghost-button" id="login-button" type="button">Login</button>
        <button class="nav-signup" id="signup-button" type="button">Sign up</button>
      </div>
    </header>

    <main>
      <section id="prototype" class="studio-stage" aria-labelledby="hero-title">
        <div class="studio-intro">
          <div>
            <p class="eyebrow">Production voice workspace</p>
            <h1 id="hero-title">Generate, review, and ship synthetic voice from one console.</h1>
            <p class="hero-lede">
              The first screen is the product: backend status, script input, voice controls, generation, playback, download, and a visible path into Vietnamese video localization.
            </p>
          </div>
          <div class="status-rail" aria-label="Live studio status">
            <article>
              <span>API</span>
              <strong>${escapeHtml(readinessLabel)}</strong>
              <small>${escapeHtml(state.baseUrl)}</small>
            </article>
            <article>
              <span>Provider</span>
              <strong>${escapeHtml(provider?.name || "checking")}</strong>
              <small>${provider?.fallback ? "fallback route visible" : "OpenAI path when ready"}</small>
            </article>
            <article>
              <span>Workflows</span>
              <strong>TTS + video</strong>
              <small>Video upload opens from the tab below</small>
            </article>
            <button
              class="secondary-button"
              id="hero-video-button"
              type="button"
              aria-label="Open video workflow"
              aria-controls="workflow-panel"
              data-testid="open-video-workflow"
            >Open video workflow</button>
          </div>
        </div>

        <section id="studio" class="studio-shell" aria-label="Prototype workspace" data-testid="prototype-studio">
          <div class="studio-toolbar">
            <div>
              <span class="mini-label">Live studio</span>
              <strong>${state.demoUser ? escapeHtml(state.demoUser) : "Public workspace"}</strong>
            </div>
            <div class="studio-stats" aria-label="Prototype status summary">
              <span>${state.voices.length.toLocaleString()} voices loaded</span>
              <span>Target Vietnamese</span>
              <span>Audio/video artifacts</span>
            </div>
            <button
              class="secondary-button mobile-video-shortcut"
              id="mobile-video-button"
              type="button"
              aria-label="Open video workflow"
              aria-controls="workflow-panel"
            >Open video workflow</button>
            <div class="health-pill ${readinessLabel === "ready" ? "is-ready" : ""}" aria-live="polite">
              <span class="status-dot" aria-hidden="true"></span>
              ${escapeHtml(readinessLabel)}
            </div>
          </div>

          <form id="settings-form" class="settings-grid" aria-label="API connection settings">
            <label class="field">
              <span>Backend API URL</span>
              <input id="base-url" type="url" value="${escapeHtml(state.baseUrl)}" autocomplete="url" />
            </label>
            <label class="field">
              <span>Backend API key</span>
              <input id="api-key" type="password" value="${escapeHtml(state.apiKey)}" autocomplete="off" placeholder="Session only; never stored" />
            </label>
            <button class="secondary-button" type="submit" ${state.voiceLoading ? "disabled" : ""}>
              ${state.voiceLoading ? "Checking..." : "Refresh backend"}
            </button>
          </form>

          <div class="workflow-switch" role="tablist" aria-label="Prototype workflow">
            <button id="workflow-tts" class="${state.activeWorkflow === "tts" ? "is-active" : ""}" type="button" role="tab" aria-selected="${state.activeWorkflow === "tts"}" aria-controls="workflow-panel" aria-label="Text to speech" data-testid="workflow-quick-tts-tab">Text to speech</button>
            <button id="workflow-video" class="${state.activeWorkflow === "video" ? "is-active" : ""}" type="button" role="tab" aria-selected="${state.activeWorkflow === "video"}" aria-controls="workflow-panel" aria-label="Video localization" data-testid="workflow-video-localization-tab">Video localization</button>
          </div>

          <div id="workflow-panel" class="workspace-grid" role="tabpanel" aria-labelledby="${state.activeWorkflow === "video" ? "workflow-video" : "workflow-tts"}">
            <div class="composer-panel">
              ${state.activeWorkflow === "video" ? videoFormMarkup() : ttsFormMarkup()}
            </div>
            <aside class="result-panel" aria-label="Output, status, and history">
              ${state.activeWorkflow === "video" ? videoOutputMarkup() : ttsOutputMarkup()}
              ${backendStatusMarkup(provider)}
              ${historyMarkup()}
            </aside>
          </div>
        </section>
      </section>

      <section id="product" class="content-section product-grid">
        <div>
          <p class="eyebrow">Product-led voice creation</p>
          <h2>Built for teams that need fast, reviewable voice output before committing to a production pipeline.</h2>
        </div>
        ${featureCard("01", "Immediate voice test", "The top screen is the working TTS flow: script, provider status, voice controls, generation, playback, and download.")}
        ${featureCard("02", "Localization path", "Video upload, transcript, SRT, dubbed audio, and final MP4 review stay available as the next workflow instead of replacing TTS.")}
        ${featureCard("03", "Studio and API posture", "Content teams get a usable product surface while developers keep the backend-configured API base and request metadata.")}
      </section>

      <section id="workflow" class="content-section workflow-explainer">
        <div>
          <p class="eyebrow">Workflow</p>
          <h2>From text preview to Vietnamese delivery package.</h2>
        </div>
        <ol class="step-list">
          <li><span>1</span><strong>Write</strong><p>Paste a script, select text or SSML mode, and keep character limits visible.</p></li>
          <li><span>2</span><strong>Tune</strong><p>Choose voice, language, format, speaking rate, pitch, and gain before spending a request.</p></li>
          <li><span>3</span><strong>Generate</strong><p>Create a voiceover with clear provider metadata, loading state, and inline errors.</p></li>
          <li><span>4</span><strong>Export</strong><p>Download transcript, SRT, audio, and final MP4 when the backend publishes artifacts.</p></li>
        </ol>
      </section>

      <section id="pricing" class="content-section">
        <div class="section-kicker">
          <p class="eyebrow">Pricing</p>
          <h2>Transparent tiers for prototype, creator, studio, and enterprise use.</h2>
        </div>
        <div class="pricing-grid">
          ${pricingCard("Free Demo", "$0", "Prototype testing", ["Short TTS previews", "Video UI demo states", "Synthetic voice disclosure included"])}
          ${pricingCard("Creator", "$29", "Solo production", ["Monthly voice minutes", "Transcript and SRT downloads", "Commercial rights subject to provider terms"])}
          ${pricingCard("Studio", "$149", "Team localization", ["Workspace history", "Batch review workflow", "Priority render queue when backend supports it"])}
          ${pricingCard("Enterprise", "Custom", "Security and scale", ["Backend-managed credentials", "Private deployment options", "Audit logs, Cloud logs, and MLflow observability"])}
        </div>
      </section>

      <section id="security" class="content-section trust-grid">
        <div>
          <p class="eyebrow">Trust and security</p>
          <h2>Designed around backend-owned secrets and observable processing.</h2>
          <p>The browser never receives OpenAI, Google, or cloud provider keys. Optional backend API keys are session-only and are not persisted.</p>
        </div>
        ${trustItem("Creators", "Preview dubs and subtitles before publishing campaign or education videos.")}
        ${trustItem("Education", "Localize lessons and training clips while keeping script review visible.")}
        ${trustItem("Sales teams", "Adapt product walkthroughs for Vietnamese prospects without manual media assembly.")}
        ${trustItem("Agencies", "Track source file, status, voice, and artifacts for client localization jobs.")}
      </section>

      <section id="docs" class="content-section docs-panel">
        <div>
          <p class="eyebrow">Docs</p>
          <h2>Backend assumptions are explicit.</h2>
          <p>TTS follows the documented /v1/voices and /v1/synthesize contract. Video localization posts file, source language, target language, and voice name to /v1/video-localization/jobs, then polls job status.</p>
        </div>
        <code>VITE_API_BASE_URL=http://&lt;api-host&gt;:8080 npm run dev -- --host 0.0.0.0 --port 5173</code>
      </section>
    </main>

    ${authPanelMarkup()}
  `;

  bindEvents();
}

function ttsFormMarkup() {
  const voice = selectedVoice();
  const languages = voice.language_codes;
  const charCount = state.text.length;

  return `
    <form id="synthesis-form" class="synthesis-form" aria-label="Synthesize speech">
      <div class="prototype-header">
        <span class="mini-label">Working first-screen workflow</span>
        <h2>Text to real voice studio</h2>
        <p>Generate speech with the current backend provider. OpenAI voices are synthetic; disclose AI-generated audio to listeners where required.</p>
      </div>
      <div class="mode-row" role="radiogroup" aria-label="Input mode">
        <label><input type="radio" name="mode" value="text" ${state.mode === "text" ? "checked" : ""} /> Plain text</label>
        <label><input type="radio" name="mode" value="ssml" ${state.mode === "ssml" ? "checked" : ""} /> SSML</label>
      </div>
      <div class="control-grid">
        <label class="field"><span>Voice</span><select id="voice-select">${state.voices
          .map((item) => `<option value="${escapeHtml(item.name)}" ${item.name === state.selectedVoiceName ? "selected" : ""}>${escapeHtml(voiceLabel(item))}</option>`)
          .join("")}</select></label>
        <label class="field"><span>Language</span><select id="language-select">${languages
          .map((language) => `<option value="${escapeHtml(language)}" ${language === state.selectedLanguage ? "selected" : ""}>${escapeHtml(language)}</option>`)
          .join("")}</select></label>
        <label class="field"><span>Encoding</span><select id="encoding-select">${selectedVoiceEncodings()
          .map((encoding) => `<option value="${escapeHtml(encoding)}" ${encoding === state.encoding ? "selected" : ""}>${escapeHtml(encoding)}</option>`)
          .join("")}</select></label>
        <label class="field"><span>Client reference</span><input id="client-reference-id" type="text" value="${escapeHtml(state.clientReferenceId)}" placeholder="script-123" /></label>
      </div>
      ${state.error ? `<div class="error-banner" role="alert">${escapeHtml(state.error)}</div>` : ""}
      <div class="action-row action-row-primary">
        <button class="primary-button" type="submit" data-testid="generate-tts-preview" ${state.synthLoading ? "disabled" : ""}>${state.synthLoading ? "Synthesizing..." : "Generate TTS preview"}</button>
        <p class="request-note">Native audio controls, no autoplay, downloadable when backend returns an artifact.</p>
      </div>
      <label class="field">
        <span>${state.mode === "ssml" ? "SSML input" : "Script input"}</span>
        <textarea id="text-input" maxlength="5000" rows="5">${escapeHtml(state.text)}</textarea>
        <small id="character-count">${charCount.toLocaleString()} / 5,000 characters</small>
      </label>
      <div class="voice-disclosure" role="note">
        <strong>AI voice disclosure</strong>
        <span>Generated audio uses synthetic voice technology. Keep consent, labeling, and commercial usage rules visible in your publishing workflow.</span>
      </div>
      <div class="slider-grid">
        ${rangeControl("speaking-rate", "Speaking rate", state.speakingRate, 0.25, 4, 0.05, "x")}
        ${rangeControl("pitch", "Pitch", state.pitch, -20, 20, 0.5, " st")}
        ${rangeControl("volume-gain-db", "Volume gain", state.volumeGainDb, -16, 16, 0.5, " dB")}
      </div>
    </form>
  `;
}

function videoFormMarkup() {
  const voices = vietnameseVoices();
  const selectedFile = state.videoFile;

  return `
    <form id="video-form" class="synthesis-form" aria-label="Localize video to Vietnamese">
      <div class="prototype-header">
        <span class="mini-label">Core test flow</span>
        <h2>Video to Vietnamese studio</h2>
        <p>Start here. Upload a source clip, choose the language and Vietnamese voice, then inspect the translation package before final export.</p>
      </div>
      <label class="field file-field command-upload">
        <span>Source video</span>
        <input id="video-file" type="file" accept="video/mp4,video/quicktime,video/webm,video/*" aria-label="Source video" aria-describedby="video-file-help" data-testid="video-file-input" />
        <strong>${selectedFile ? escapeHtml(selectedFile.name) : "Drop a Chinese or English video into the localization queue"}</strong>
        <small id="video-file-help">${selectedFile ? `${formatNumber(selectedFile.size, " bytes")} selected. Start localization when ready.` : "MP4, MOV, M4V, or WebM up to 250 MB. Use short clips for the fastest acceptance pass."}</small>
      </label>
      <div class="control-grid video-controls">
        <label class="field"><span>Source language</span><select id="video-source-language">
          <option value="en-US" ${state.videoSourceLanguage === "en-US" ? "selected" : ""}>English (US)</option>
          <option value="en" ${state.videoSourceLanguage === "en" ? "selected" : ""}>English</option>
          <option value="zh-CN" ${state.videoSourceLanguage === "zh-CN" ? "selected" : ""}>Chinese (Simplified)</option>
          <option value="zh" ${state.videoSourceLanguage === "zh" ? "selected" : ""}>Chinese</option>
        </select></label>
        <label class="field"><span>Target</span><input type="text" value="Vietnamese script, SRT, dub, MP4" disabled /></label>
        <label class="field"><span>Vietnamese voice</span><select id="video-target-voice">${voices
          .map((voice) => `<option value="${escapeHtml(voice.name)}" ${voice.name === selectedVideoVoice().name ? "selected" : ""}>${escapeHtml(voiceLabel(voice))}</option>`)
          .join("")}</select></label>
        <label class="field"><span>Client reference</span><input id="video-client-reference-id" type="text" value="${escapeHtml(state.videoClientReferenceId)}" placeholder="pilot-video-01" /></label>
      </div>
      <label class="check-row">
        <input id="video-burn-subtitles" type="checkbox" ${state.videoBurnSubtitles ? "checked" : ""} />
        Burn Vietnamese subtitles into final video when backend supports rendering
      </label>
      ${state.videoError ? `<div class="error-banner" role="alert">${escapeHtml(state.videoError)}</div>` : ""}
      <div class="action-row">
        <button class="primary-button" type="submit" aria-label="Start Vietnamese localization" data-testid="start-video-localization" ${state.videoLoading ? "disabled" : ""}>${state.videoLoading ? "Starting localization..." : "Start Vietnamese localization"}</button>
      </div>
      <div class="pipeline-preview" aria-label="Localization pipeline stages">
        ${pipelineStepsMarkup(state.videoJob?.stage)}
      </div>
    </form>
  `;
}

function ttsOutputMarkup() {
  return `
    <section class="panel-section">
      <div class="section-heading"><h2>TTS output</h2><span>${state.latest?.status || "No job yet"}</span></div>
      ${
        state.synthLoading
          ? skeletonOutput()
          : state.latest
            ? outputMarkup()
            : `<div class="empty-state"><p>No audio yet. Paste text, choose a voice, and generate a preview to see the player and download link here.</p></div>`
      }
    </section>
  `;
}

function outputMarkup() {
  const latest = state.latest!;
  const audioUrl = state.latestAudioUrl;
  return `
    <div class="audio-card">
      ${audioUrl ? `<audio controls preload="metadata" src="${escapeAttribute(audioUrl)}">Your browser does not support audio playback.</audio><a class="download-link" href="${escapeAttribute(audioUrl)}" download>Download audio</a>` : `<div class="empty-state small"><p>The backend did not return an audio URL or path.</p></div>`}
      <dl class="metadata-list">
        <div><dt>Job ID</dt><dd data-testid="tts-job-id">${escapeHtml(latest.job_id)}</dd></div>
        <div><dt>Latency</dt><dd>${formatNumber(latest.latency_ms, " ms")}</dd></div>
        <div><dt>Duration</dt><dd>${formatNumber(latest.duration_ms, " ms")}</dd></div>
        <div><dt>Audio</dt><dd>${escapeHtml(latest.audio?.encoding || state.encoding)} · ${formatNumber(latest.audio?.bytes, " bytes")}</dd></div>
        <div><dt>Request ID</dt><dd>${escapeHtml(latest.observability?.request_id || "Not reported")}</dd></div>
      </dl>
    </div>
  `;
}

function videoOutputMarkup() {
  const job = state.videoJob;
  const artifacts = videoArtifactUrls(job);
  const progress = Math.max(0, Math.min(100, Math.round(job?.progress ?? (job?.status === "succeeded" ? 100 : 0))));
  const scriptEditable = job?.script?.editable === true;
  const jobError = typeof job?.error === "string" ? job.error : job?.error?.message;
  const warnings = [...(job?.warnings || []), ...(job?.observability?.warnings || [])];
  return `
    <section class="panel-section">
      <div class="section-heading"><h2>Localization output</h2><span>${escapeHtml(job?.status || "Ready to test")}</span></div>
      ${
        state.videoLoading
          ? skeletonOutput()
          : job
            ? `<div class="video-job-card">
                <div class="progress-shell" aria-label="Video localization progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}" role="progressbar"><span style="width: ${progress}%"></span></div>
                <p class="stage-line">${escapeHtml(job.stage || job.message || "Waiting for backend status updates.")}</p>
                ${jobError ? `<div class="error-banner" role="alert">${escapeHtml(jobError)}</div>` : ""}
                ${warnings.length ? `<div class="warning-list" role="note">${warnings.map((warning) => `<span>${escapeHtml(warning)}</span>`).join("")}</div>` : ""}
                <div class="agent-plan" aria-label="Processing plan">
                  ${pipelineStepsMarkup(job.stage)}
                </div>
                <div class="artifact-grid">
                  ${downloadButton("Transcript", artifacts.transcript)}
                  ${downloadButton("SRT", artifacts.srt)}
                  ${downloadButton("VTT", artifacts.vtt)}
                  ${downloadButton("Vietnamese audio", artifacts.audio)}
                  ${downloadButton("Final MP4", artifacts.video)}
                </div>
                ${artifacts.audio ? `<audio controls preload="metadata" src="${escapeAttribute(artifacts.audio)}">Your browser does not support audio playback.</audio>` : ""}
                ${artifacts.video ? `<video controls preload="metadata" src="${escapeAttribute(artifacts.video)}">Your browser does not support video playback.</video>` : `<div class="video-placeholder">Final video preview appears here when the backend publishes MP4 output.</div>`}
                <label class="field"><span>Vietnamese script preview</span><textarea id="video-script-editor" rows="6" placeholder="Vietnamese script appears here after transcription and translation." ${scriptEditable ? "" : "readonly"}>${escapeHtml(state.videoScript)}</textarea></label>
                <label class="field"><span>Vietnamese SRT preview</span><textarea id="video-srt-editor" rows="6" placeholder="Timed Vietnamese subtitles appear here." ${scriptEditable ? "" : "readonly"}>${escapeHtml(state.videoSrt)}</textarea></label>
                <dl class="metadata-list">
                  <div><dt>Job ID</dt><dd data-testid="video-job-id">${escapeHtml(job.job_id)}</dd></div>
                  <div><dt>Source</dt><dd>${escapeHtml(job.source_language || state.videoSourceLanguage)}</dd></div>
                  <div><dt>Target</dt><dd>${escapeHtml(job.target_language || "vi")}</dd></div>
                  <div><dt>Provider</dt><dd>${escapeHtml(job.provider?.name || "Not reported")}${job.provider?.fallback ? " (fallback)" : ""}</dd></div>
                  <div><dt>Updated</dt><dd>${escapeHtml(job.updated_at || "Not reported")}</dd></div>
                  <div><dt>Request ID</dt><dd>${escapeHtml(job.observability?.request_id || "Not reported")}</dd></div>
                  <div><dt>MLflow</dt><dd>${escapeHtml(job.observability?.mlflow_run_id || "Not reported")}</dd></div>
                </dl>
              </div>`
            : `<div class="empty-state"><p>Upload a short Chinese or English video to inspect backend progress, Vietnamese previews, media players, and download links here.</p></div>`
      }
    </section>
  `;
}

function backendStatusMarkup(provider?: { name?: string; ready?: boolean; fallback?: boolean }) {
  return `
    <section class="panel-section compact">
      <div class="section-heading"><h2>Backend status</h2><button class="text-button" id="status-refresh" type="button">Check</button></div>
      <dl class="metadata-list">
        <div><dt>Provider</dt><dd>${escapeHtml(provider?.name || "Fallback/demo")}${provider?.fallback ? " (fallback)" : ""}</dd></div>
        <div><dt>Provider ready</dt><dd>${provider?.ready === undefined ? "Unknown" : provider.ready ? "Yes" : "No"}</dd></div>
        <div><dt>Storage</dt><dd>${escapeHtml(state.readiness?.storage?.mode || "Unknown")} ${state.readiness?.storage?.ready === false ? "(not ready)" : ""}</dd></div>
        <div><dt>MLflow</dt><dd>${state.readiness?.mlflow?.configured ? "Configured" : "Not configured"} ${state.readiness?.mlflow?.ready === false ? "(not ready)" : ""}</dd></div>
      </dl>
    </section>
  `;
}

function historyMarkup() {
  const isVideo = state.activeWorkflow === "video";
  return `
    <section class="panel-section compact">
      <div class="section-heading">
        <h2>${isVideo ? "Video jobs" : "TTS history"}</h2>
        <button class="text-button" id="clear-history" type="button" ${isVideo ? (state.videoHistory.length ? "" : "disabled") : state.history.length ? "" : "disabled"}>Clear</button>
      </div>
      ${
        isVideo
          ? state.videoHistory.length
            ? `<ol class="history-list">${state.videoHistory.map(videoHistoryItem).join("")}</ol>`
            : `<div class="empty-state small"><p>No video jobs in this browser yet.</p></div>`
          : state.history.length
            ? `<ol class="history-list">${state.history.map(historyItem).join("")}</ol>`
            : `<div class="empty-state small"><p>No TTS jobs in this browser yet.</p></div>`
      }
    </section>
  `;
}

function rangeControl(id: string, label: string, value: number, min: number, max: number, step: number, suffix: string) {
  return `<label class="field range-field"><span>${label}</span><input id="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${value}" /><output for="${id}">${value}${suffix}</output></label>`;
}

function skeletonOutput() {
  return `<div class="skeleton-block" aria-live="polite"><span></span><span></span><span></span></div>`;
}

function downloadButton(label: string, href: string) {
  return href
    ? `<a class="download-link artifact-card" href="${escapeAttribute(href)}" download><span>${escapeHtml(label)}</span><small>Ready</small></a>`
    : `<span class="artifact-missing artifact-card" aria-disabled="true"><span>${escapeHtml(label)}</span><small>Pending</small></span>`;
}

function pipelineStepsMarkup(currentStage?: string) {
  const current = (currentStage || "").toLowerCase();
  const stages = [
    ["Upload", "source file", ["upload", "uploaded", "queued"]],
    ["Extract", "audio track", ["extract", "audio"]],
    ["Transcribe", "source speech", ["transcribe", "transcription", "speech"]],
    ["Translate", "Vietnamese script", ["translate", "translation"]],
    ["Subtitle", "timed SRT", ["subtitle", "srt", "vtt"]],
    ["Dub", "Vietnamese voice", ["dub", "voice", "synth", "tts"]],
    ["Render", "final MP4", ["render", "mux", "mp4", "complete", "succeeded"]]
  ] as const;
  const foundIndex = stages.findIndex(([, , keywords]) => keywords.some((keyword) => current.includes(keyword)));
  const activeIndex = Math.max(0, foundIndex);

  return stages
    .map(([label, detail], index) => {
      const isActive = index === activeIndex;
      const isDone = foundIndex >= 0 && index < activeIndex;
      return `<div class="plan-step ${isActive ? "is-active" : ""} ${isDone ? "is-done" : ""}"><span>${index + 1}</span><strong>${label}</strong><small>${detail}</small></div>`;
    })
    .join("");
}

function historyItem(item: HistoryItem) {
  const created = new Date(item.createdAt).toLocaleString();
  return `<li><div><strong>${escapeHtml(item.jobId)}</strong><p>${escapeHtml(item.textPreview)}</p><span>${escapeHtml(item.voice)} · ${escapeHtml(item.encoding)} · ${escapeHtml(created)}</span></div>${item.audioUrl ? `<a href="${escapeAttribute(item.audioUrl)}" download>Download</a>` : ""}</li>`;
}

function videoHistoryItem(item: VideoHistoryItem) {
  const created = new Date(item.createdAt).toLocaleString();
  const href = item.videoUrl || item.audioUrl || item.srtUrl || item.transcriptUrl;
  return `<li><div><strong>${escapeHtml(item.jobId)}</strong><p>${escapeHtml(item.fileName)} with ${escapeHtml(item.targetVoice)}</p><span>${escapeHtml(item.status)} · ${escapeHtml(item.sourceLanguage)} to vi · ${escapeHtml(created)}</span></div>${href ? `<a href="${escapeAttribute(href)}" download>Download</a>` : ""}</li>`;
}

function featureCard(index: string, title: string, body: string) {
  return `<article class="feature-card"><span>${index}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p></article>`;
}

function pricingCard(name: string, price: string, subtitle: string, items: string[]) {
  return `<article class="pricing-card"><h3>${escapeHtml(name)}</h3><strong>${escapeHtml(price)}</strong><p>${escapeHtml(subtitle)}</p><ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article>`;
}

function trustItem(title: string, body: string) {
  return `<article class="trust-item"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p></article>`;
}

function authPanelMarkup() {
  if (!state.showAuthPanel) {
    return "";
  }
  const isRegister = state.authMode === "register";
  return `
    <div class="auth-backdrop" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <form id="auth-form" class="auth-card">
        <button class="auth-close" id="auth-close" type="button" aria-label="Close auth panel">Close</button>
        <p class="eyebrow">Demo workspace</p>
        <h2 id="auth-title">${isRegister ? "Create a demo account" : "Login to demo workspace"}</h2>
        <p>No backend auth endpoint is documented yet. This creates a local demo identity only and stores no secrets.</p>
        <label class="field"><span>Email</span><input id="auth-email" type="email" autocomplete="email" placeholder="you@company.com" required /></label>
        <label class="field"><span>Password</span><input id="auth-password" type="password" autocomplete="${isRegister ? "new-password" : "current-password"}" placeholder="Not sent to backend in demo mode" required /></label>
        <button class="primary-button" type="submit">${isRegister ? "Enter demo workspace" : "Login to demo"}</button>
        <button class="text-button" id="auth-toggle" type="button">${isRegister ? "Use login instead" : "Create demo account"}</button>
      </form>
    </div>
  `;
}

function bindEvents() {
  document.querySelector<HTMLButtonElement>("#workflow-tts")?.addEventListener("click", () => {
    switchWorkflow("tts");
  });
  document.querySelector<HTMLButtonElement>("#workflow-video")?.addEventListener("click", () => {
    switchWorkflow("video", { focusUpload: true });
  });
  document.querySelector<HTMLButtonElement>("#hero-video-button")?.addEventListener("click", () => {
    switchWorkflow("video", { scroll: true, focusUpload: true });
  });
  document.querySelector<HTMLButtonElement>("#mobile-video-button")?.addEventListener("click", () => {
    switchWorkflow("video", { focusUpload: true });
  });
  document.querySelector<HTMLButtonElement>("#login-button")?.addEventListener("click", () => {
    state.authMode = "login";
    state.showAuthPanel = true;
    render();
  });
  document.querySelector<HTMLButtonElement>("#signup-button")?.addEventListener("click", () => {
    state.authMode = "register";
    state.showAuthPanel = true;
    render();
  });
  document.querySelector<HTMLButtonElement>("#auth-close")?.addEventListener("click", () => {
    state.showAuthPanel = false;
    render();
  });
  document.querySelector<HTMLButtonElement>("#auth-toggle")?.addEventListener("click", () => {
    state.authMode = state.authMode === "register" ? "login" : "register";
    render();
  });
  document.querySelector<HTMLFormElement>("#auth-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const email = document.querySelector<HTMLInputElement>("#auth-email")?.value || "Demo user";
    state.demoUser = email;
    localStorage.setItem(storageKeys.demoUser, email);
    state.showAuthPanel = false;
    render();
  });

  document.querySelector<HTMLFormElement>("#settings-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.baseUrl = normalizeBaseUrl(document.querySelector<HTMLInputElement>("#base-url")?.value || defaultBaseUrl);
    state.apiKey = document.querySelector<HTMLInputElement>("#api-key")?.value || "";
    saveSettings();
    void refreshStatus();
  });

  document.querySelector<HTMLFormElement>("#synthesis-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    void synthesize();
  });
  document.querySelector<HTMLFormElement>("#video-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    void startVideoLocalization();
  });
  document.querySelectorAll<HTMLInputElement>('input[name="mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.mode = input.value === "ssml" ? "ssml" : "text";
      render();
    });
  });
  document.querySelector<HTMLTextAreaElement>("#text-input")?.addEventListener("input", (event) => {
    state.text = (event.target as HTMLTextAreaElement).value;
    const count = document.querySelector<HTMLElement>("#character-count");
    if (count) count.textContent = `${state.text.length.toLocaleString()} / 5,000 characters`;
  });
  document.querySelector<HTMLSelectElement>("#voice-select")?.addEventListener("change", (event) => {
    state.selectedVoiceName = (event.target as HTMLSelectElement).value;
    const voice = selectedVoice();
    state.selectedLanguage = voice.language_codes[0];
    const encodings = selectedVoiceEncodings();
    if (!encodings.includes(state.encoding)) state.encoding = encodings[0];
    render();
  });
  document.querySelector<HTMLSelectElement>("#language-select")?.addEventListener("change", (event) => {
    state.selectedLanguage = (event.target as HTMLSelectElement).value;
  });
  document.querySelector<HTMLSelectElement>("#encoding-select")?.addEventListener("change", (event) => {
    state.encoding = (event.target as HTMLSelectElement).value;
  });
  document.querySelector<HTMLInputElement>("#client-reference-id")?.addEventListener("input", (event) => {
    state.clientReferenceId = (event.target as HTMLInputElement).value;
  });

  document.querySelector<HTMLInputElement>("#video-file")?.addEventListener("change", (event) => {
    const file = (event.target as HTMLInputElement).files?.[0] || null;
    const validationError = validateVideoFile(file);
    state.videoFile = validationError ? null : file;
    state.videoError = file ? validationError : "";
    render();
  });
  document.querySelector<HTMLSelectElement>("#video-source-language")?.addEventListener("change", (event) => {
    state.videoSourceLanguage = (event.target as HTMLSelectElement).value as AppState["videoSourceLanguage"];
  });
  document.querySelector<HTMLSelectElement>("#video-target-voice")?.addEventListener("change", (event) => {
    state.videoTargetVoiceName = (event.target as HTMLSelectElement).value;
  });
  document.querySelector<HTMLInputElement>("#video-client-reference-id")?.addEventListener("input", (event) => {
    state.videoClientReferenceId = (event.target as HTMLInputElement).value;
  });
  document.querySelector<HTMLInputElement>("#video-burn-subtitles")?.addEventListener("change", (event) => {
    state.videoBurnSubtitles = (event.target as HTMLInputElement).checked;
  });
  document.querySelector<HTMLTextAreaElement>("#video-script-editor")?.addEventListener("input", (event) => {
    state.videoScript = (event.target as HTMLTextAreaElement).value;
  });
  document.querySelector<HTMLTextAreaElement>("#video-srt-editor")?.addEventListener("input", (event) => {
    state.videoSrt = (event.target as HTMLTextAreaElement).value;
  });

  bindRange("#speaking-rate", (value) => (state.speakingRate = value));
  bindRange("#pitch", (value) => (state.pitch = value));
  bindRange("#volume-gain-db", (value) => (state.volumeGainDb = value));

  document.querySelector<HTMLButtonElement>("#status-refresh")?.addEventListener("click", () => void refreshStatus());
  document.querySelector<HTMLButtonElement>("#clear-history")?.addEventListener("click", () => {
    if (state.activeWorkflow === "tts") {
      state.history = [];
      saveHistory();
    } else {
      state.videoHistory = [];
      saveVideoHistory();
    }
    render();
  });
}

function bindRange(selector: string, onChange: (value: number) => void) {
  document.querySelector<HTMLInputElement>(selector)?.addEventListener("input", (event) => {
    const input = event.target as HTMLInputElement;
    const value = Number(input.value);
    onChange(value);
    const output = input.closest(".range-field")?.querySelector("output");
    if (output) {
      const suffix = selector === "#speaking-rate" ? "x" : selector === "#pitch" ? " st" : " dB";
      output.textContent = `${value}${suffix}`;
    }
  });
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttribute(value: string) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

render();
void refreshStatus();
