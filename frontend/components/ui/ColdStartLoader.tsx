"use client";

import { useEffect, useState } from "react";
import { SkeletonCard } from "./Skeleton";

interface ColdStartLoaderProps {
  /** Number of skeleton cards to render. */
  count?: number;
}

/**
 * Skeleton loader with progressive messaging for backend cold-starts.
 *
 * Render Free tier can take 30-60s to wake up. Without feedback, users
 * assume the page is broken and leave. This component:
 * - Shows a subtle "読み込み中" after 2s
 * - Shows "サーバーを起動中" with explanation after 5s
 * - Shows "もう少しお待ちください" after 15s
 */
export function ColdStartLoader({ count = 4 }: ColdStartLoaderProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 500);
    return () => clearInterval(interval);
  }, []);

  const phase =
    elapsed < 2 ? 0 : elapsed < 5 ? 1 : elapsed < 15 ? 2 : 3;

  return (
    <div className="space-y-6">
      {/* Status banner */}
      {phase >= 1 && (
        <div
          className="glass-sm p-4 flex items-start gap-3 transition-opacity duration-300"
          aria-live="polite"
        >
          <div className="shrink-0 mt-0.5">
            <div className="relative h-5 w-5">
              <div className="absolute inset-0 rounded-full border-2 border-accent/20" />
              <div className="absolute inset-0 rounded-full border-2 border-accent border-t-transparent animate-spin" />
            </div>
          </div>
          <div className="flex-1 space-y-1">
            {phase === 1 && (
              <>
                <p className="text-sm text-text-primary">読み込み中...</p>
                <p className="text-xs text-text-muted">
                  特徴量カタログを取得しています
                </p>
              </>
            )}
            {phase === 2 && (
              <>
                <p className="text-sm text-text-primary">
                  サーバーを起動しています
                </p>
                <p className="text-xs text-text-muted">
                  初回アクセスはサーバー起動に30秒ほどかかります。もう少々お待ちください。
                </p>
              </>
            )}
            {phase === 3 && (
              <>
                <p className="text-sm text-text-primary">
                  もう少しお待ちください
                </p>
                <p className="text-xs text-text-muted">
                  通常より時間がかかっています。経過時間: {elapsed}秒 /
                  最大90秒
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* Skeleton cards */}
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: count }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}
