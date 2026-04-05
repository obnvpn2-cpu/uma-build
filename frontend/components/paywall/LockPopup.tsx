"use client";

import type { LockedFeature } from "@/lib/types";
import { Lock } from "lucide-react";

interface LockPopupProps {
  lockedFeatures: LockedFeature[];
}

export function LockPopup({ lockedFeatures }: LockPopupProps) {
  if (!lockedFeatures.length) return null;

  return (
    <div className="glass p-4 space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <Lock className="w-4 h-4 text-warning" />
        Pro限定機能
      </h3>
      <div className="space-y-2">
        {lockedFeatures.map((feature) => (
          <div
            key={feature.id}
            className="glass-sm flex items-start gap-3 p-3"
          >
            <Lock className="w-4 h-4 text-text-muted mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-text-primary">
                {feature.name}
              </p>
              <p className="text-xs text-text-muted">{feature.description}</p>
            </div>
          </div>
        ))}
      </div>
      <a
        href="/pricing"
        className="btn-primary block text-center text-sm px-4 py-2 rounded-lg cursor-pointer"
      >
        Proプランで全機能を解放
      </a>
    </div>
  );
}
