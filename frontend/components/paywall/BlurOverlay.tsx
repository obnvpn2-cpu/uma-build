"use client";

import { useEffect, type ReactNode } from "react";
import { sendEvent } from "@/lib/gtm";

interface BlurOverlayProps {
  children: ReactNode;
  isLocked: boolean;
  message?: string;
  section?: string;
}

export function BlurOverlay({ children, isLocked, message, section }: BlurOverlayProps) {
  useEffect(() => {
    if (isLocked) {
      sendEvent("paywall_impression", { section: section || "unknown" });
    }
  }, [isLocked, section]);

  if (!isLocked) return <>{children}</>;

  const handleClick = () => {
    sendEvent("paywall_click", { section: section || "unknown" });
  };

  return (
    <div className="relative" onClick={handleClick}>
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
