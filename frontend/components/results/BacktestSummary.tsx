"use client";

import type { LearnSummary } from "@/lib/types";
import { ReliabilityStars } from "./ReliabilityStars";

interface BacktestSummaryProps {
  summary: LearnSummary;
}

export function BacktestSummary({ summary }: BacktestSummaryProps) {
  const roi = summary.roi ?? 0;
  const hitRate = summary.hit_rate ?? 0;
  const nRaces = summary.n_races ?? 0;
  const stars = summary.reliability_stars ?? 1;

  return (
    <div className="glass-strong p-6 space-y-4">
      <h3 className="font-mincho text-lg font-bold text-glow-yellow">
        バックテスト結果
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="space-y-1">
          <p className="text-xs text-text-muted">回収率 (ROI)</p>
          <p
            className={`text-2xl font-mono font-bold ${
              roi >= 100 ? "text-success" : "text-danger"
            }`}
            style={{
              filter:
                roi >= 100
                  ? "drop-shadow(0 0 10px rgba(74,222,128,0.5))"
                  : "drop-shadow(0 0 10px rgba(248,113,113,0.45))",
            }}
          >
            {roi.toFixed(1)}%
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-text-muted">的中率</p>
          <p
            className="text-2xl font-mono font-bold text-accent"
            style={{ filter: "drop-shadow(0 0 10px rgba(245,233,50,0.5))" }}
          >
            {hitRate.toFixed(1)}%
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-text-muted">対象レース数</p>
          <p className="text-2xl font-mono font-bold text-text-primary">
            {nRaces.toLocaleString()}
          </p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-text-muted">実戦信頼度</p>
          <ReliabilityStars stars={stars} />
        </div>
      </div>
    </div>
  );
}
