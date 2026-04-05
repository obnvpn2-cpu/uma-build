"use client";

import type { BreakdownItem } from "@/lib/types";

interface ConditionBreakdownProps {
  data: BreakdownItem[];
  isBlurred: boolean;
}

export function ConditionBreakdown({ data, isBlurred }: ConditionBreakdownProps) {
  return (
    <div className="glass p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">条件別パフォーマンス</h3>
        {isBlurred && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/40">
            Pro で詳細表示
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-text-muted text-xs">
              <th className="text-left py-2 pr-4">条件</th>
              <th className="text-right py-2 px-2">購入数</th>
              <th className="text-right py-2 px-2">的中率</th>
              <th className="text-right py-2 px-2">回収率</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, i) => {
              const label =
                [item.surface, item.track_condition].filter(Boolean).join("・") ||
                item.distance_category ||
                `Row ${i}`;
              const rowBlurred = item.is_blurred;
              return (
                <tr key={i} className="border-b border-white/5">
                  <td className="py-2 pr-4 text-text-primary">{label}</td>
                  <td className="text-right py-2 px-2 font-mono text-text-secondary">
                    {item.n_bets}
                  </td>
                  <td
                    className={`text-right py-2 px-2 font-mono ${
                      rowBlurred ? "blur-overlay" : "text-text-secondary"
                    }`}
                  >
                    {item.hit_rate?.toFixed(1)}%
                  </td>
                  <td
                    className={`text-right py-2 px-2 font-mono ${
                      rowBlurred ? "blur-overlay" : ""
                    } ${
                      !rowBlurred && item.roi !== null
                        ? item.roi >= 100
                          ? "text-success"
                          : "text-danger"
                        : "text-text-muted"
                    }`}
                  >
                    {rowBlurred
                      ? "---%"
                      : item.roi !== null
                      ? `${item.roi.toFixed(1)}%`
                      : "---"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
