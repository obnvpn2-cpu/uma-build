import { API_BASE } from "@/lib/api";

// Edge Runtime + ISR + Stale-While-Revalidate
// 目的: Render Free のコールドスタート(50s+)を /lab ロード経路から完全排除する。
// 特徴量カタログは静的なので Vercel Edge にキャッシュし、/lab ロード時は Render を一切叩かない。
export const runtime = "edge";
export const revalidate = 3600; // 1時間ごとに背景で再検証

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/features`, {
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
        // s-maxage: Edge cache 1時間 / SWR: 期限切れでも24時間は即座に返す
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    });
  } catch {
    // Render が死んでいても直近キャッシュが SWR で返るため通常ここには来ない。
    // 初回デプロイ直後のキャッシュミス時のフェイルセーフ。
    return new Response(
      JSON.stringify({ detail: "backend unavailable" }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}
