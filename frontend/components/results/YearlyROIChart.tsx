"use client";

import type { BreakdownItem } from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

interface YearlyROIChartProps {
  data: BreakdownItem[];
  isBlurred: boolean;
}

export function YearlyROIChart({ data, isBlurred }: YearlyROIChartProps) {
  const chartData = data.map((item) => ({
    name: item.year ? String(item.year) : "N/A",
    roi:
      item.roi ??
      (item as unknown as Record<string, unknown>).placeholder ??
      Math.random() * 30 + 80,
    hitRate: item.hit_rate,
    nBets: item.n_bets,
  }));

  return (
    <div className="glass p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">年別回収率</h3>
        {isBlurred && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/40">
            Pro で詳細表示
          </span>
        )}
      </div>
      <div className={isBlurred ? "blur-overlay" : ""}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.08)"
            />
            <XAxis dataKey="name" stroke="#B4B4BE" fontSize={12} />
            <YAxis
              stroke="#B4B4BE"
              fontSize={12}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(20,20,30,0.85)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                border: "1px solid rgba(245,233,50,0.3)",
                borderRadius: 12,
                fontSize: 12,
                boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
              }}
              labelStyle={{ color: "#F5F5F7", fontWeight: 600 }}
              itemStyle={{ color: "#F5E932" }}
              cursor={{ fill: "rgba(245,233,50,0.08)" }}
            />
            <ReferenceLine
              y={100}
              stroke="rgba(180,180,190,0.6)"
              strokeDasharray="3 3"
              label={{
                value: "100%",
                fill: "#B4B4BE",
                fontSize: 10,
              }}
            />
            <defs>
              <linearGradient id="roiBarGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FFF373" stopOpacity={1} />
                <stop offset="100%" stopColor="#E0D020" stopOpacity={0.85} />
              </linearGradient>
            </defs>
            <Bar
              dataKey="roi"
              fill="url(#roiBarGradient)"
              radius={[6, 6, 0, 0]}
              name="回収率(%)"
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill="url(#roiBarGradient)" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
