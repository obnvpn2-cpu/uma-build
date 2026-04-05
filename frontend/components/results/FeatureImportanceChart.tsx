"use client";

import type { FeatureImportanceItem, FeatureCategory } from "@/lib/types";

interface FeatureImportanceChartProps {
  data: FeatureImportanceItem[];
  isBlurred: boolean;
  categories?: FeatureCategory[];
}

export function FeatureImportanceChart({ data, isBlurred, categories }: FeatureImportanceChartProps) {
  const maxImportance = Math.max(...data.map((d) => d.importance ?? 10), 1);
  const sorted = [...data].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).slice(0, 10);

  // Build feature ID → Japanese label map from categories
  const labelMap = new Map<string, string>();
  if (categories) {
    for (const cat of categories) {
      for (const f of cat.features) {
        labelMap.set(f.id, f.label);
      }
    }
  }

  return (
    <div className="glass p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">特徴量重要度 Top10</h3>
        {isBlurred && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/40">
            Pro で詳細表示
          </span>
        )}
      </div>
      <div className={`space-y-2 ${isBlurred ? "blur-overlay" : ""}`}>
        {sorted.map((item) => {
          const width = maxImportance > 0 ? ((item.importance ?? 5) / maxImportance) * 100 : 50;
          return (
            <div key={item.feature} className="flex items-center gap-2">
              <span className="text-xs text-text-secondary w-32 truncate text-right">
                {labelMap.get(item.feature) ?? item.feature}
              </span>
              <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                <div
                  className="h-full rounded"
                  style={{
                    width: `${width}%`,
                    background:
                      "linear-gradient(90deg, #FFF373 0%, #F5E932 60%, #E0D020 100%)",
                    boxShadow: "0 0 10px rgba(245,233,50,0.35)",
                  }}
                />
              </div>
              <span className="text-xs font-mono text-text-muted w-10 text-right">
                {item.importance !== null ? item.importance.toFixed(1) : "?"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
