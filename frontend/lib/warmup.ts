import { API_BASE } from "./api";

let warmupTriggered = false;

/**
 * Fire-and-forget ping to wake up the backend.
 *
 * Render Free tier sleeps after 15 min of inactivity and cold-start can take
 * up to 60s. By pinging /api/health as soon as the app mounts (even on the
 * home page), we give the backend a head start so that when the user reaches
 * /lab the features query is likely to hit a warm server.
 *
 * Safe to call multiple times — only the first call actually fires.
 */
export function warmupBackend(): void {
  if (typeof window === "undefined") return;
  if (warmupTriggered) return;
  warmupTriggered = true;

  // Use keepalive so the request survives navigation; swallow all errors
  // because this is a best-effort warmup.
  fetch(`${API_BASE}/api/health`, {
    method: "GET",
    keepalive: true,
  }).catch(() => {
    // Reset so a subsequent call can retry if needed.
    warmupTriggered = false;
  });
}
