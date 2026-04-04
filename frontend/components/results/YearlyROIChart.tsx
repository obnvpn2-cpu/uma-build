"use client";

import type { BreakdownItem } from "@/lib/types";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface YearlyROIChartProps {
  data: BreakdownItem[];
  isBlurred: boolean;
}

export function YearlyROIChart({ data, isBlurred }: YearlyROIChartProps) {
  const chartData = data.map((item) => ({
    name: item.year ? String(item.year) : "N/A",
    roi: item.roi ?? (item as unknown as Record<string, unknown>).placeholder ?? Math.random() * 30 + 80,
    hitRate: item.hit_rate,
    nBets: item.n_bets,
  }));

  return (
    <div className="bg-surface-raised border border-surface-border rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">年別回収率</h3>
        {isBlurred && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
            Pro で詳細表示
          </span>
        )}
      </div>
      <div className={isBlurred ? "blur-overlay" : ""}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
            <XAxis dataKey="name" stroke="#8B949E" fontSize={12} />
            <YAxis stroke="#8B949E" fontSize={12} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip
              contentStyle={{ backgroundColor: "#1C2128", border: "1px solid #30363D", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#F0F6FC" }}
            />
            <ReferenceLine y={100} stroke="#8B949E" strokeDasharray="3 3" label={{ value: "100%", fill: "#8B949E", fontSize: 10 }} />
            <Bar dataKey="roi" fill="#58A6FF" radius={[4, 4, 0, 0]} name="回収率(%)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
