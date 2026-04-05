"use client";

import type { FeatureCategory } from "@/lib/types";
import { FeatureCategoryCard } from "./FeatureCategoryCard";

interface FeatureSelectorProps {
  categories: FeatureCategory[];
  selectedIds: Set<string>;
  onToggleFeature: (id: string) => void;
  onToggleAll: (categoryId: string, featureIds: string[], selectAll: boolean) => void;
  onResetDefaults: () => void;
}

export function FeatureSelector({
  categories,
  selectedIds,
  onToggleFeature,
  onToggleAll,
  onResetDefaults,
}: FeatureSelectorProps) {
  const totalFeatures = categories.reduce((s, c) => s + c.features.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-mincho text-lg font-bold text-glow-yellow">
            特徴量を選択
          </h2>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-xs text-text-muted">
              AIが学習に使うデータ項目を選びましょう
            </p>
            <span
              className="inline-flex items-center gap-1 text-xs font-mono px-2.5 py-1 rounded-full bg-accent/15 text-accent border border-accent/40"
              style={{ boxShadow: "0 0 14px rgba(245,233,50,0.25)" }}
            >
              <span className="font-bold">{selectedIds.size}</span>
              <span className="text-accent/60">/ {totalFeatures}</span>
              <span className="text-accent/80 ml-0.5">選択中</span>
            </span>
          </div>
        </div>
        <button
          onClick={onResetDefaults}
          className="glass-sm text-xs px-3 py-2 text-text-secondary hover:text-accent transition cursor-pointer min-h-[36px]"
        >
          デフォルトに戻す
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {categories.map((cat) => (
          <FeatureCategoryCard
            key={cat.id}
            id={cat.id}
            name={cat.name}
            description={cat.description}
            icon={cat.icon}
            features={cat.features}
            selectedIds={selectedIds}
            onToggleFeature={onToggleFeature}
            onToggleAll={onToggleAll}
          />
        ))}
      </div>
    </div>
  );
}
