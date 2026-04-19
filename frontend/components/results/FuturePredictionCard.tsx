"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { FuturePredictionRace } from "@/lib/types";
import { ProBadge } from "@/components/paywall/ProBadge";

interface FuturePredictionCardProps {
  races: FuturePredictionRace[];
}

const confidenceColor = {
  high: "text-success",
  medium: "text-accent",
  low: "text-text-muted",
} as const;

const confidenceLabel = {
  high: "高",
  medium: "中",
  low: "低",
} as const;

export function FuturePredictionCard({ races }: FuturePredictionCardProps) {
  const [openRaces, setOpenRaces] = useState<Set<string>>(
    new Set(races.slice(0, 1).map((r) => r.race_key))
  );

  const toggle = (key: string) => {
    setOpenRaces((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="glass-strong p-6 space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="font-mincho text-lg font-bold text-glow-yellow">
          未来レース予測
        </h3>
        <ProBadge />
      </div>
      <p className="text-xs text-text-muted">
        訓練済みモデルによる次開催の予測ランキング
      </p>

      <div className="space-y-3">
        {races.map((race) => {
          const isOpen = openRaces.has(race.race_key);
          return (
            <div key={race.race_key} className="glass-sm overflow-hidden">
              <button
                onClick={() => toggle(race.race_key)}
                className="w-full flex items-center justify-between p-3 hover:bg-white/5 transition cursor-pointer"
              >
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-accent font-semibold">
                    {race.race_name}
                  </span>
                  <span className="text-text-muted font-mono text-xs">
                    {race.race_date}
                  </span>
                  <span className="text-text-muted text-xs">
                    {race.surface} {race.distance}m
                  </span>
                </div>
                {isOpen ? (
                  <ChevronUp className="w-4 h-4 text-text-muted" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-muted" />
                )}
              </button>

              {isOpen && (
                <div className="px-3 pb-3">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10 text-text-muted text-xs">
                        <th className="text-left py-2 w-8">#</th>
                        <th className="text-left py-2">馬名</th>
                        <th className="text-left py-2 hidden sm:table-cell">
                          騎手
                        </th>
                        <th className="text-center py-2 w-10">枠</th>
                        <th className="text-left py-2 w-32 sm:w-40">
                          AIスコア
                        </th>
                        <th className="text-center py-2 w-12">信頼度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {race.entries.map((entry, i) => {
                        const isTop = i === 0;
                        const maxScore = race.entries[0]?.predicted_score ?? 1;
                        const barWidth =
                          maxScore > 0
                            ? (entry.predicted_score / maxScore) * 100
                            : 0;
                        return (
                          <tr
                            key={entry.rank}
                            className={`border-b border-white/5 ${
                              isTop ? "bg-accent/5" : ""
                            }`}
                          >
                            <td
                              className={`py-2 font-mono font-bold ${
                                isTop ? "text-accent" : "text-text-secondary"
                              }`}
                            >
                              {entry.rank}
                            </td>
                            <td
                              className={`py-2 ${
                                isTop
                                  ? "text-accent font-semibold"
                                  : "text-text-primary"
                              }`}
                            >
                              {entry.horse_name}
                            </td>
                            <td className="py-2 text-text-muted hidden sm:table-cell">
                              {entry.jockey}
                            </td>
                            <td className="py-2 text-center font-mono text-text-secondary">
                              {entry.gate_number}
                            </td>
                            <td className="py-2">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                                  <div
                                    className="h-full rounded-full"
                                    style={{
                                      width: `${barWidth}%`,
                                      background: isTop
                                        ? "linear-gradient(90deg, #58A6FF, #F5E932)"
                                        : "linear-gradient(90deg, #58A6FF 0%, #58A6FF 100%)",
                                      opacity: isTop ? 1 : 0.6,
                                    }}
                                  />
                                </div>
                                <span className="font-mono text-xs text-text-muted w-10 text-right">
                                  {entry.predicted_score.toFixed(3)}
                                </span>
                              </div>
                            </td>
                            <td className="py-2 text-center">
                              <span
                                className={`text-xs font-semibold ${
                                  confidenceColor[entry.confidence]
                                }`}
                              >
                                {confidenceLabel[entry.confidence]}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
