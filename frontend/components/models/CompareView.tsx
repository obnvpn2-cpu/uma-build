"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { CompareResponse } from "@/lib/types";

interface CompareViewProps {
  data: CompareResponse;
  onClose: () => void;
}

const MODEL_COLORS = ["#F5E932", "#58A6FF", "#3ECF8E", "#F97583", "#D2A8FF"];

export function CompareView({ data, onClose }: CompareViewProps) {
  const { models, feature_diff } = data;

  // Find best ROI model
  const bestRoi = useMemo(() => {
    let best = -Infinity;
    let bestId = "";
    for (const m of models) {
      const roi = m.summary?.roi ?? -Infinity;
      if (roi > best) {
        best = roi;
        bestId = m.model_id ?? "";
      }
    }
    return bestId;
  }, [models]);

  // Build yearly comparison chart data
  const yearlyChartData = useMemo(() => {
    const yearMap = new Map<number, Record<string, number | string>>();
    for (const m of models) {
      const yearly = m.yearly_breakdown ?? [];
      for (const item of yearly) {
        if (item.is_blurred || item.year === undefined) continue;
        const existing = yearMap.get(item.year) || { year: item.year };
        existing[m.name ?? m.model_id ?? ""] = item.roi ?? 0;
        yearMap.set(item.year, existing);
      }
    }
    return Array.from(yearMap.values()).sort(
      (a, b) => (a.year as number) - (b.year as number),
    );
  }, [models]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-mincho text-xl font-bold">モデル比較</h2>
        <button
          onClick={onClose}
          className="glass-sm px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary transition cursor-pointer"
        >
          ✕ 閉じる
        </button>
      </div>

      {/* Summary cards grid */}
      <div
        className="grid gap-4"
        style={{
          gridTemplateColumns: `repeat(${Math.min(models.length, 3)}, minmax(0, 1fr))`,
        }}
      >
        {models.map((m, i) => {
          const isBest = (m.model_id ?? "") === bestRoi;
          const roi = m.summary?.roi;
          const roiColor =
            roi !== null && roi !== undefined
              ? roi >= 100
                ? "text-success"
                : "text-danger"
              : "text-text-muted";

          return (
            <div
              key={m.model_id ?? i}
              className={`glass p-4 space-y-2 relative ${
                isBest ? "border-accent/50" : ""
              }`}
              style={
                isBest
                  ? { boxShadow: "0 0 20px rgba(245, 233, 50, 0.15)" }
                  : undefined
              }
            >
              {isBest && (
                <span className="absolute -top-2 right-3 text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent border border-accent/30">
                  Best ROI
                </span>
              )}
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length] }}
                />
                <h3 className="text-sm font-semibold truncate">
                  {m.name ?? "無題"}
                </h3>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-text-muted">ROI</span>
                  <span className={`font-mono font-bold ${roiColor}`}>
                    {roi !== null && roi !== undefined ? `${roi.toFixed(1)}%` : "---"}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-text-muted">的中率</span>
                  <span className="font-mono text-text-secondary">
                    {m.summary?.hit_rate !== null && m.summary?.hit_rate !== undefined
                      ? `${m.summary.hit_rate.toFixed(1)}%`
                      : "---"}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-text-muted">信頼度</span>
                  <span>
                    {Array.from({ length: 5 }, (_, j) => (
                      <span
                        key={j}
                        className={
                          j < (m.summary?.reliability_stars ?? 0)
                            ? "star-filled"
                            : "star-empty"
                        }
                      >
                        ★
                      </span>
                    ))}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-text-muted">特徴量数</span>
                  <span className="font-mono text-text-secondary">
                    {m.feature_ids?.length ?? "---"}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Yearly ROI comparison chart */}
      {yearlyChartData.length > 0 && (
        <div className="glass p-4 space-y-3">
          <h3 className="text-sm font-semibold">年別ROI比較</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={yearlyChartData} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="year" tick={{ fill: "#b4b4be", fontSize: 12 }} />
                <YAxis tick={{ fill: "#b4b4be", fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(13, 17, 23, 0.95)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 8,
                    color: "#f5f5f7",
                  }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(value: any) => [`${Number(value).toFixed(1)}%`, ""]}
                />
                <Legend />
                {models.map((m, i) => (
                  <Bar
                    key={m.model_id ?? i}
                    dataKey={m.name ?? m.model_id ?? `model-${i}`}
                    fill={MODEL_COLORS[i % MODEL_COLORS.length]}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Feature diff */}
      <div className="glass p-4 space-y-3">
        <h3 className="text-sm font-semibold">特徴量の差分</h3>

        {/* Common features */}
        {feature_diff.common.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-text-muted">
              共通（{feature_diff.common.length}個）
            </p>
            <div className="flex flex-wrap gap-1.5">
              {feature_diff.common.map((f) => (
                <span
                  key={f}
                  className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-text-secondary"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Unique features per model */}
        {Object.entries(feature_diff.unique).map(([modelId, features], i) => {
          if (features.length === 0) return null;
          const modelName =
            models.find((m) => m.model_id === modelId)?.name ?? modelId;
          return (
            <div key={modelId} className="space-y-1.5">
              <p className="text-xs text-text-muted flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length] }}
                />
                {modelName}のみ（{features.length}個）
              </p>
              <div className="flex flex-wrap gap-1.5">
                {features.map((f) => (
                  <span
                    key={f}
                    className="text-xs px-2 py-0.5 rounded-full border text-text-primary"
                    style={{
                      borderColor: `${MODEL_COLORS[i % MODEL_COLORS.length]}40`,
                      backgroundColor: `${MODEL_COLORS[i % MODEL_COLORS.length]}10`,
                    }}
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Feature importance side-by-side */}
      {models.some((m) => m.feature_importance && m.feature_importance.length > 0) && (
        <div className="glass p-4 space-y-3">
          <h3 className="text-sm font-semibold">特徴量重要度（Top 5）</h3>
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: `repeat(${Math.min(models.length, 3)}, minmax(0, 1fr))`,
            }}
          >
            {models.map((m, i) => (
              <div key={m.model_id ?? i} className="space-y-2">
                <p className="text-xs text-text-muted flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: MODEL_COLORS[i % MODEL_COLORS.length] }}
                  />
                  {m.name ?? "無題"}
                </p>
                {(m.feature_importance ?? [])
                  .filter((fi) => !fi.is_blurred)
                  .slice(0, 5)
                  .map((fi, j) => (
                    <div
                      key={j}
                      className="flex items-center justify-between text-xs"
                    >
                      <span className="text-text-secondary truncate mr-2">
                        {fi.feature}
                      </span>
                      <span className="font-mono text-text-primary">
                        {fi.importance?.toFixed(3) ?? "---"}
                      </span>
                    </div>
                  ))}
                {(!m.feature_importance || m.feature_importance.length === 0) && (
                  <p className="text-xs text-text-muted">データなし</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
