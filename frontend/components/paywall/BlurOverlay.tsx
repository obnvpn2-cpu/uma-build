"use client";

import type { ReactNode } from "react";

interface BlurOverlayProps {
  children: ReactNode;
  isLocked: boolean;
  message?: string;
}

export function BlurOverlay({ children, isLocked, message }: BlurOverlayProps) {
  if (!isLocked) return <>{children}</>;

  return (
    <div className="relative">
      <div className="blur-overlay">{children}</div>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="glass-strong px-6 py-4 text-center max-w-xs">
          <p className="text-sm text-text-primary font-medium">
            {message || "Proプランで完全な結果を確認できます"}
          </p>
          <a
            href="/pricing"
            className="btn-primary inline-block mt-3 text-xs px-4 py-1.5 rounded-full cursor-pointer"
          >
            Proプランを見る
          </a>
        </div>
      </div>
    </div>
  );
}
