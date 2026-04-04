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
        <div className="bg-surface-raised/90 backdrop-blur-sm border border-accent/30 rounded-xl px-6 py-4 text-center max-w-xs">
          <p className="text-sm text-text-primary font-medium">
            {message || "Proプランで完全な結果を確認できます"}
          </p>
          <a
            href="/pricing"
            className="inline-block mt-2 text-xs px-4 py-1.5 rounded-full bg-accent text-surface font-medium hover:bg-accent-dark transition cursor-pointer"
          >
            Proプランを見る
          </a>
        </div>
      </div>
    </div>
  );
}
