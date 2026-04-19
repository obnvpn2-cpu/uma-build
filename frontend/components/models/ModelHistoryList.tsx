"use client";

import { useState } from "react";
import type { SavedModel } from "@/lib/types";

interface ModelHistoryListProps {
  models: SavedModel[];
  selectedIds: Set<string>;
  onToggleSelect: (modelId: string) => void;
  onDelete: (modelId: string) => void;
  onRename: (modelId: string, newName: string) => void;
}

export function ModelHistoryList({
  models,
  selectedIds,
  onToggleSelect,
  onDelete,
  onRename,
}: ModelHistoryListProps) {
  if (models.length === 0) {
    return (
      <div className="glass-strong p-8 text-center space-y-3">
        <div className="text-4xl">📦</div>
        <h3 className="font-mincho text-lg font-bold">
          まだ保存したモデルがありません
        </h3>
        <p className="text-sm text-text-secondary">
          AI Labでモデルを学習して保存すると、ここに表示されます
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {models.map((model) => (
        <ModelCard
          key={model.id}
          model={model}
          isSelected={selectedIds.has(model.model_id)}
          onToggleSelect={() => onToggleSelect(model.model_id)}
          onDelete={() => onDelete(model.model_id)}
          onRename={(newName) => onRename(model.model_id, newName)}
        />
      ))}
    </div>
  );
}

function ModelCard({
  model,
  isSelected,
  onToggleSelect,
  onDelete,
  onRename,
}: {
  model: SavedModel;
  isSelected: boolean;
  onToggleSelect: () => void;
  onDelete: () => void;
  onRename: (newName: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(model.name);
  const [confirming, setConfirming] = useState(false);

  const roiColor =
    model.roi !== null
      ? model.roi >= 100
        ? "text-success"
        : "text-danger"
      : "text-text-muted";

  const stars = model.reliability_stars ?? 0;

  return (
    <div
      className={`glass p-4 transition-all ${
        isSelected ? "border-accent/40 bg-accent/5" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <label className="flex items-center pt-1 cursor-pointer">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            className="w-4 h-4 rounded border-white/20 bg-white/5 accent-[var(--accent)] cursor-pointer"
          />
        </label>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {editing ? (
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onBlur={() => {
                  if (editName.trim() && editName !== model.name) {
                    onRename(editName.trim());
                  }
                  setEditing(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    if (editName.trim() && editName !== model.name) {
                      onRename(editName.trim());
                    }
                    setEditing(false);
                  }
                  if (e.key === "Escape") {
                    setEditName(model.name);
                    setEditing(false);
                  }
                }}
                maxLength={100}
                className="bg-white/5 border border-white/10 rounded px-2 py-0.5 text-sm text-text-primary focus:outline-none focus:border-accent/50"
                autoFocus
              />
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="text-sm font-semibold text-text-primary hover:text-accent transition truncate cursor-pointer text-left"
                title="クリックして名前を編集"
              >
                {model.name}
              </button>
            )}
          </div>

          {/* Metrics row */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <span className={`font-mono font-bold ${roiColor}`}>
              ROI {model.roi !== null ? `${model.roi.toFixed(1)}%` : "---"}
            </span>
            <span className="text-text-secondary font-mono">
              的中率 {model.hit_rate !== null ? `${model.hit_rate.toFixed(1)}%` : "---"}
            </span>
            <span className="text-text-muted">
              {Array.from({ length: 5 }, (_, i) => (
                <span key={i} className={i < stars ? "star-filled" : "star-empty"}>
                  ★
                </span>
              ))}
            </span>
            <span className="text-text-muted">
              特徴量: {model.n_features ?? "---"}個
            </span>
            <span className="text-text-muted">
              {new Date(model.created_at).toLocaleDateString("ja-JP")}
            </span>
          </div>
        </div>

        {/* Delete */}
        <div className="flex-shrink-0">
          {confirming ? (
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  onDelete();
                  setConfirming(false);
                }}
                className="text-xs text-danger hover:underline cursor-pointer"
              >
                削除
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="text-xs text-text-muted hover:text-text-secondary cursor-pointer"
              >
                戻る
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="text-text-muted hover:text-danger transition cursor-pointer p-1"
              title="削除"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
