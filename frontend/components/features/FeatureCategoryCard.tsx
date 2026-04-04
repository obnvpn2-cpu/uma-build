"use client";

import type { Feature } from "@/lib/types";
import { FeatureChip } from "./FeatureChip";
import {
  Flag,
  TrendingUp,
  Scale,
  BarChart3,
  Trophy,
  PersonStanding,
  GraduationCap,
  Dna,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  "🏁": Flag,
  "🐴": TrendingUp,
  "⚖️": Scale,
  "📊": BarChart3,
  "🏆": Trophy,
  "🏇": PersonStanding,
  "👨‍🏫": GraduationCap,
  "🧬": Dna,
};

interface FeatureCategoryCardProps {
  id: string;
  name: string;
  description: string;
  icon: string;
  features: Feature[];
  selectedIds: Set<string>;
  onToggleFeature: (id: string) => void;
  onToggleAll: (categoryId: string, featureIds: string[], selectAll: boolean) => void;
}

export function FeatureCategoryCard({
  id,
  name,
  description,
  icon,
  features,
  selectedIds,
  onToggleFeature,
  onToggleAll,
}: FeatureCategoryCardProps) {
  const featureIds = features.map((f) => f.id);
  const selectedCount = featureIds.filter((fid) => selectedIds.has(fid)).length;
  const allSelected = selectedCount === features.length;

  const IconComponent = ICON_MAP[icon];

  return (
    <div className="bg-surface-raised border border-surface-border rounded-xl p-4 space-y-3 flex flex-col min-h-[200px]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {IconComponent ? (
            <IconComponent className="w-5 h-5 text-accent" />
          ) : (
            <span className="text-lg">{icon}</span>
          )}
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{name}</h3>
            <p className="text-xs text-text-muted">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-mono px-2 py-0.5 rounded-full transition-colors ${
              selectedCount > 0
                ? "bg-accent/15 text-accent border border-accent/30"
                : "text-text-muted"
            }`}
          >
            {selectedCount}/{features.length}
          </span>
          <button
            onClick={() => onToggleAll(id, featureIds, !allSelected)}
            className="text-xs px-3 py-2 rounded border border-surface-border text-text-secondary hover:text-accent hover:border-accent/40 transition cursor-pointer min-h-[36px]"
          >
            {allSelected ? "全OFF" : "全ON"}
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-auto pt-1">
        {features.map((feature) => (
          <FeatureChip
            key={feature.id}
            id={feature.id}
            label={feature.label}
            description={feature.description}
            isSelected={selectedIds.has(feature.id)}
            onToggle={onToggleFeature}
          />
        ))}
      </div>
    </div>
  );
}
