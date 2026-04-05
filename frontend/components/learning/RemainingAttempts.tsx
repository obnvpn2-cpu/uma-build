"use client";

interface RemainingAttemptsProps {
  used: number;
  max: number;
  isPro: boolean;
}

export function RemainingAttempts({ used, max, isPro }: RemainingAttemptsProps) {
  const remaining = Math.max(0, max - used);
  const ratio = max > 0 ? used / max : 0;

  return (
    <div className="flex items-center gap-3 text-sm">
      <div className="flex items-center gap-1.5">
        <span className="text-text-muted">本日の残り回数:</span>
        <span className={`font-mono font-bold ${remaining <= 1 ? "text-danger" : remaining <= 3 ? "text-warning" : "text-accent"}`}>
          {remaining}
        </span>
        <span className="text-text-muted">/ {max}</span>
      </div>
      <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${ratio >= 0.8 ? "bg-danger" : ratio >= 0.5 ? "bg-warning" : "bg-accent"}`}
          style={{
            width: `${ratio * 100}%`,
            boxShadow:
              ratio < 0.5 ? "0 0 8px rgba(245,233,50,0.5)" : undefined,
          }}
        />
      </div>
      {!isPro && remaining <= 1 && (
        <span className="text-xs text-warning">Proで上限緩和</span>
      )}
    </div>
  );
}
