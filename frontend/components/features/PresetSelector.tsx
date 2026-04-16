"use client";

import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/api";
import { sendEvent } from "@/lib/gtm";

interface Preset {
  id: string;
  name: string;
  description: string;
  icon: string;
  features: string[];
}

interface PresetSelectorProps {
  onApply: (featureIds: string[]) => void;
}

async function fetchPresets(): Promise<Preset[]> {
  const res = await fetch(`${API_BASE}/api/features/presets`);
  if (!res.ok) throw new Error("Failed to fetch presets");
  return res.json();
}

export function PresetSelector({ onApply }: PresetSelectorProps) {
  const { data: presets, isLoading } = useQuery<Preset[]>({
    queryKey: ["feature-presets"],
    queryFn: fetchPresets,
  });

  if (isLoading || !presets) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
        プリセットテンプレート
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {presets.map((preset) => (
          <button
            key={preset.id}
            onClick={() => {
              onApply(preset.features);
              sendEvent("preset_apply", {
                preset_id: preset.id,
                feature_count: preset.features.length,
              });
            }}
            className="glass-sm p-3 text-left hover:bg-white/10 transition cursor-pointer group"
          >
            <div className="text-lg mb-1">{preset.icon}</div>
            <p className="text-xs font-medium text-text-primary group-hover:text-accent transition">
              {preset.name}
            </p>
            <p className="text-[10px] text-text-muted mt-0.5 line-clamp-2">
              {preset.description}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
