declare global {
  interface Window {
    dataLayer: Record<string, unknown>[];
  }
}

export function sendEvent(event: string, params?: Record<string, unknown>) {
  if (typeof window !== "undefined" && window.dataLayer) {
    window.dataLayer.push({ event, ...params });
  }
}
