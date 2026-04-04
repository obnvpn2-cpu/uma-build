import type { FeatureCategory, JobStatusResponse, LearnRequest, LearnResponse, LimitsResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  return res.json();
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
