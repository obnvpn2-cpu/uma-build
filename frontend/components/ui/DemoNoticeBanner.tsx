"use client";

export function DemoNoticeBanner() {
  return (
    <div className="w-full rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-center">
      <p className="text-sm font-semibold text-amber-400">
        本結果は合成デモデータに基づく参考値です
      </p>
      <p className="text-xs text-amber-400/70 mt-1">
        実際のレースデータとは異なります。回収率・的中率は実データ接続後に現実的な値になります。
      </p>
    </div>
  );
}
