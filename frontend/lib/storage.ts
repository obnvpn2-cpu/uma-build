const PREFIX = "umabuild_";

function getKey(key: string): string {
  return `${PREFIX}${key}`;
}

export function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  const key = getKey("session_id");
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export function getSelectedFeatures(): string[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(getKey("selected_features"));
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function setSelectedFeatures(ids: string[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(getKey("selected_features"), JSON.stringify(ids));
}

export function getLastModelId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(getKey("last_model_id"));
}

export function setLastModelId(id: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(getKey("last_model_id"), id);
}

export function getDailyAttempts(): number {
  if (typeof window === "undefined") return 0;
  const raw = localStorage.getItem(getKey("daily_attempts"));
  if (!raw) return 0;
  try {
    const data = JSON.parse(raw);
    const today = new Date().toISOString().slice(0, 10);
    if (data.date !== today) return 0;
    return data.count || 0;
  } catch {
    return 0;
  }
}

export function incrementDailyAttempts(): number {
  const today = new Date().toISOString().slice(0, 10);
  const current = getDailyAttempts();
  const newCount = current + 1;
  localStorage.setItem(
    getKey("daily_attempts"),
    JSON.stringify({ date: today, count: newCount })
  );
  return newCount;
}
