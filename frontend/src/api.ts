export type Voice = {
  name: string;
  language_codes: string[];
  ssml_gender?: string;
  natural_sample_rate_hz?: number;
  supported_encodings?: string[];
};

export type VoicesResponse = {
  provider?: string;
  voices: Voice[];
};

export type ProviderStatus = {
  name?: string;
  ready?: boolean;
  fallback?: boolean;
  model?: string;
};

export type ReadinessResponse = {
  status?: string;
  provider?: ProviderStatus;
  storage?: { mode?: string; ready?: boolean };
  mlflow?: { configured?: boolean; ready?: boolean };
};

export type SynthesizeRequest = {
  text: string | null;
  ssml: string | null;
  voice: {
    language_code: string;
    name?: string;
    ssml_gender?: string;
  };
  audio: {
    encoding: string;
    speaking_rate: number;
    pitch: number;
    volume_gain_db: number;
    sample_rate_hz?: number;
  };
  metadata: {
    client_reference_id?: string;
  };
};

export type SynthesizeResponse = {
  job_id: string;
  status: string;
  audio_url?: string;
  audio_path?: string;
  duration_ms?: number;
  latency_ms?: number;
  provider?: ProviderStatus;
  voice?: {
    language_code?: string;
    name?: string;
    ssml_gender?: string;
  };
  audio?: {
    encoding?: string;
    bytes?: number;
    sample_rate_hz?: number;
    checksum_sha256?: string;
  };
  observability?: {
    request_id?: string;
    mlflow_run_id?: string;
  };
  metadata?: {
    client_reference_id?: string;
  };
};

export type VideoLocalizationRequest = {
  video: File;
  source_language: "zh" | "zh-CN" | "en" | "en-US";
  target_language: "vi";
  target_voice_name?: string;
  target_voice_language_code?: string;
  generate_subtitles: boolean;
  burn_subtitles: boolean;
  metadata?: {
    client_reference_id?: string;
  };
};

export type VideoLocalizationJob = {
  job_id: string;
  status: "queued" | "processing" | "needs_review" | "succeeded" | "failed" | string;
  progress?: number;
  stage?: string;
  message?: string;
  source_language?: string;
  target_language?: string;
  script?: {
    vietnamese_text?: string;
    srt?: string;
    editable?: boolean;
  };
  artifacts?: {
    transcript_url?: string;
    transcript_path?: string;
    srt_url?: string;
    srt_path?: string;
    audio_url?: string;
    audio_path?: string;
    video_url?: string;
    video_path?: string;
  };
  observability?: {
    request_id?: string;
  };
  created_at?: string;
  updated_at?: string;
};

export type ApiClientOptions = {
  baseUrl: string;
  apiKey?: string;
};

export class ApiError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly requestId?: string;
  readonly jobId?: string;

  constructor(message: string, options: { status?: number; code?: string; requestId?: string; jobId?: string } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId;
    this.jobId = options.jobId;
  }
}

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

export const normalizeBaseUrl = (value: string) => {
  const trimmed = value.trim();
  return trimTrailingSlash(trimmed || "http://localhost:8080");
};

export const resolveAudioUrl = (baseUrl: string, audioUrl?: string, audioPath?: string) => {
  if (audioUrl) {
    return new URL(audioUrl, `${normalizeBaseUrl(baseUrl)}/`).toString();
  }

  if (audioPath) {
    const filename = audioPath.split("/").filter(Boolean).pop();
    if (filename) {
      return `${normalizeBaseUrl(baseUrl)}/audio/${encodeURIComponent(filename)}`;
    }
  }

  return "";
};

export const resolveArtifactUrl = (baseUrl: string, directUrl?: string, artifactPath?: string, route = "artifacts") => {
  if (directUrl) {
    return new URL(directUrl, `${normalizeBaseUrl(baseUrl)}/`).toString();
  }

  if (artifactPath) {
    const filename = artifactPath.split("/").filter(Boolean).pop();
    if (filename) {
      return `${normalizeBaseUrl(baseUrl)}/${route}/${encodeURIComponent(filename)}`;
    }
  }

  return "";
};

export const formatApiError = async (response: Response) => {
  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  const jobId = response.headers.get("X-Job-ID") ?? undefined;

  try {
    const body = await response.json();
    const error = body?.error;
    return new ApiError(error?.message || `Request failed with status ${response.status}`, {
      status: response.status,
      code: error?.code,
      requestId: body?.request_id || requestId,
      jobId: body?.job_id || jobId
    });
  } catch {
    return new ApiError(`Request failed with status ${response.status}`, {
      status: response.status,
      requestId,
      jobId
    });
  }
};

const requestId = () => {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  if (globalThis.crypto && typeof globalThis.crypto.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex
      .slice(8, 10)
      .join("")}-${hex.slice(10, 16).join("")}`;
  }

  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

export class VoiceAiClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;

  constructor(options: ApiClientOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.apiKey = options.apiKey?.trim() || undefined;
  }

  async health() {
    return this.request<{ status?: string; service?: string; version?: string }>("/healthz", false);
  }

  async readiness() {
    return this.request<ReadinessResponse>("/readyz", false);
  }

  async voices(languageCode?: string) {
    const query = languageCode ? `?language_code=${encodeURIComponent(languageCode)}` : "";
    return this.request<VoicesResponse>(`/v1/voices${query}`, true);
  }

  async synthesize(payload: SynthesizeRequest, idempotencyKey?: string) {
    return this.request<SynthesizeResponse>("/v1/synthesize", true, {
      method: "POST",
      body: JSON.stringify(payload),
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined
    });
  }

  async startVideoLocalization(payload: VideoLocalizationRequest, idempotencyKey?: string) {
    const body = new FormData();
    body.set("file", payload.video);
    body.set("source_language", payload.source_language);
    body.set("target_language", payload.target_language);
    if (payload.target_voice_name) {
      body.set("voice_name", payload.target_voice_name);
    }
    if (payload.metadata?.client_reference_id) {
      body.set("client_reference_id", payload.metadata.client_reference_id);
    }

    return this.request<VideoLocalizationJob>("/v1/video-localization/jobs", true, {
      method: "POST",
      body,
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined
    });
  }

  async videoLocalizationJob(jobId: string) {
    return this.request<VideoLocalizationJob>(`/v1/video-localization/jobs/${encodeURIComponent(jobId)}`, true);
  }

  private async request<T>(path: string, authenticated: boolean, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (authenticated && this.apiKey) {
      headers.set("Authorization", `Bearer ${this.apiKey}`);
    }
    headers.set("X-Request-ID", `web_${requestId()}`);

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers
      });
    } catch {
      throw new ApiError(`Cannot reach backend at ${this.baseUrl}. Check the API base URL and CORS settings.`);
    }

    if (!response.ok) {
      throw await formatApiError(response);
    }

    return response.json() as Promise<T>;
  }
}
