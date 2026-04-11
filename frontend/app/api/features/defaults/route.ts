import { API_BASE } from "@/lib/api";

// Edge Runtime + ISR + Stale-While-Revalidate
// /api/features と同じパターンで、デフォルト特徴量セットを Edge にキャッシュする。
export const runtime = "edge";
export const revalidate = 3600;

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/features/defaults`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) {
      throw new Error(`Backend error: ${res.status}`);
    }
    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    });
  } catch {
    return new Response(
      JSON.stringify({ detail: "backend unavailable" }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}
