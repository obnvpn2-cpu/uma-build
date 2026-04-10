import type { FeatureCategory, JobStatusResponse, LearnRequest, LearnResponse, LimitsResponse } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Default fetch timeout. Covers Render Free cold starts (up to ~60s). */
const DEFAULT_TIMEOUT_MS = 90_000;

async function fetchAPI<T>(
  path: string,
  options?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `API error: ${res.status}`);
    }

    return res.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(
        "サーバーの応答がタイムアウトしました。ページを再読み込みしてお試しください。",
      );
    }
    if (err instanceof TypeError) {
      // Network error (server unreachable, CORS, etc.)
      throw new Error(
        "サーバーに接続できません。しばらく待ってから再度お試しください。",
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchFeatures(): Promise<FeatureCategory[]> {
  return fetchAPI<FeatureCategory[]>("/api/features");
}

export async function fetchDefaults(): Promise<{ default_features: string[]; count: number }> {
  return fetchAPI("/api/features/defaults");
}

export async function postLearn(request: LearnRequest): Promise<{ job_id: string; status: string }> {
  return fetchAPI<{ job_id: string; status: string }>("/api/learn", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function pollJobStatus(jobId: string): Promise<JobStatusResponse> {
  return fetchAPI<JobStatusResponse>(
    `/api/learn/status/${encodeURIComponent(jobId)}`
  );
}

export async function fetchLimits(sessionId: string, isPro: boolean): Promise<LimitsResponse> {
  return fetchAPI<LimitsResponse>(
    `/api/learn/limits?session_id=${encodeURIComponent(sessionId)}&is_pro=${isPro}`
  );
}

export async function fetchResults(modelId: string, isPro: boolean): Promise<LearnResponse> {
  return fetchAPI<LearnResponse>(
    `/api/results/${encodeURIComponent(modelId)}?is_pro=${isPro}`
  );
}
