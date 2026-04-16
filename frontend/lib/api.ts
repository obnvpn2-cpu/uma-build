import type { FeatureCategory, JobStatusResponse, LearnRequest, LearnResponse, LimitsResponse } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Default fetch timeout. Covers Render Free cold starts (up to ~60s). */
const DEFAULT_TIMEOUT_MS = 90_000;

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  try {
    // Dynamic import to avoid pulling supabase into Edge runtime
    const { supabase } = await import("./supabase");
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` };
    }
  } catch {
    // Auth not available — continue without token
  }
  return {};
}

async function fetchWithTimeout<T>(
  url: string,
  options?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
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

async function fetchAPI<T>(
  path: string,
  options?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const mergedOptions = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(options?.headers || {}),
    },
  };
  return fetchWithTimeout<T>(`${API_BASE}${path}`, mergedOptions, timeoutMs);
}

/**
 * 同一オリジンの Next.js ルートハンドラ経由で fetch する。
 * Edge Cache 化した `/api/features` 系を叩くために使う。
 * ブラウザ実行時は相対パス、SSR時は API_BASE を経由せず同一オリジンに解決させる。
 */
async function fetchRelative<T>(
  path: string,
  options?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const url =
    typeof window !== "undefined"
      ? `${window.location.origin}${path}`
      : path;
  return fetchWithTimeout<T>(url, options, timeoutMs);
}

export async function fetchFeatures(): Promise<FeatureCategory[]> {
  // Next.js Edge ルート経由 → Vercel Edge Cache から即応答
  return fetchRelative<FeatureCategory[]>("/api/features");
}

export async function fetchDefaults(): Promise<{ default_features: string[]; count: number }> {
  // Next.js Edge ルート経由 → Vercel Edge Cache から即応答
  return fetchRelative("/api/features/defaults");
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

export async function fetchLimits(sessionId: string): Promise<LimitsResponse> {
  return fetchAPI<LimitsResponse>(
    `/api/learn/limits?session_id=${encodeURIComponent(sessionId)}`
  );
}

export async function fetchResults(modelId: string): Promise<LearnResponse> {
  return fetchAPI<LearnResponse>(
    `/api/results/${encodeURIComponent(modelId)}`
  );
}
