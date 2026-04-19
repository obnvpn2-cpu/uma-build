"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { saveModel } from "@/lib/api";

interface SaveModelButtonProps {
  modelId: string | null;
  featureIds: string[];
  onSaved?: () => void;
  onError?: (msg: string) => void;
}

export function SaveModelButton({ modelId, featureIds, onSaved, onError }: SaveModelButtonProps) {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  if (!modelId) return null;

  // Not logged in
  if (!user) {
    return (
      <div className="glass-sm px-4 py-3 flex items-center justify-between">
        <span className="text-sm text-text-secondary">
          このモデルを保存して後で比較できます
        </span>
        <button
          onClick={() => {
            // Trigger auth modal via custom event
            window.dispatchEvent(new CustomEvent("open-auth-modal"));
          }}
          className="text-sm text-accent hover:underline cursor-pointer"
        >
          ログインして保存
        </button>
      </div>
    );
  }

  // Already saved
  if (saved) {
    return (
      <div className="glass-sm px-4 py-3 flex items-center justify-between">
        <span className="text-sm text-success flex items-center gap-1.5">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          保存しました
        </span>
        <Link
          href="/lab/models"
          className="text-sm text-accent hover:underline"
        >
          マイモデル →
        </Link>
      </div>
    );
  }

  // Inline save form
  if (isOpen) {
    return (
      <div className="glass-sm px-4 py-3 space-y-3">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="モデル名を入力..."
            maxLength={100}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && !saving) handleSave();
              if (e.key === "Escape") setIsOpen(false);
            }}
          />
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary px-4 py-2 rounded-lg text-sm whitespace-nowrap"
          >
            {saving ? "保存中..." : "保存"}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="text-text-muted hover:text-text-secondary text-sm cursor-pointer"
          >
            ✕
          </button>
        </div>
      </div>
    );
  }

  async function handleSave() {
    if (!modelId) return;
    setSaving(true);
    try {
      await saveModel(modelId, name || "無題のモデル", featureIds);
      setSaved(true);
      onSaved?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "保存に失敗しました";
      onError?.(msg);
    } finally {
      setSaving(false);
    }
  }

  // Default: show save button
  return (
    <div className="glass-sm px-4 py-3 flex items-center justify-between">
      <span className="text-sm text-text-secondary">
        このモデルを保存して後で比較
      </span>
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-1.5 text-sm text-accent hover:text-accent-light transition cursor-pointer"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
        </svg>
        モデルを保存
      </button>
    </div>
  );
}
