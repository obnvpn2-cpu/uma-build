"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/hooks/useAuth";
import { useSavedModels } from "@/hooks/useSavedModels";
import { compareModels } from "@/lib/api";
import type { CompareResponse } from "@/lib/types";
import { ModelHistoryList } from "@/components/models/ModelHistoryList";
import { CompareButton } from "@/components/models/CompareButton";
import { CompareView } from "@/components/models/CompareView";
import { AuthModal } from "@/components/auth/AuthModal";
import { Toast } from "@/components/ui/Toast";

export default function ModelsPage() {
  const { user, loading: authLoading } = useAuth();
  const { models, limit, isLoading, error, remove, rename } = useSavedModels(!!user);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [comparing, setComparing] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);

  const handleToggleSelect = useCallback((modelId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) {
        next.delete(modelId);
      } else if (next.size < 5) {
        next.add(modelId);
      }
      return next;
    });
  }, []);

  const handleDelete = useCallback(
    async (modelId: string) => {
      try {
        await remove(modelId);
        setSelectedIds((prev) => {
          const next = new Set(prev);
          next.delete(modelId);
          return next;
        });
        setToast({ message: "モデルを削除しました", type: "info" });
      } catch {
        setToast({ message: "削除に失敗しました", type: "error" });
      }
    },
    [remove],
  );

  const handleRename = useCallback(
    async (modelId: string, newName: string) => {
      try {
        await rename(modelId, newName);
      } catch {
        setToast({ message: "名前の変更に失敗しました", type: "error" });
      }
    },
    [rename],
  );

  const handleCompare = useCallback(async () => {
    if (selectedIds.size < 2) return;
    setComparing(true);
    try {
      const result = await compareModels(Array.from(selectedIds));
      setCompareData(result);
    } catch (e) {
      setToast({
        message: e instanceof Error ? e.message : "比較に失敗しました",
        type: "error",
      });
    } finally {
      setComparing(false);
    }
  }, [selectedIds]);

  // Loading
  if (authLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="glass-strong p-8 text-center">
          <div className="text-text-muted animate-pulse">読み込み中...</div>
        </div>
      </div>
    );
  }

  // Not logged in
  if (!user) {
    return (
      <>
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="glass-strong p-8 text-center space-y-4">
            <div className="text-4xl">🔒</div>
            <h2 className="font-mincho text-xl font-bold">ログインが必要です</h2>
            <p className="text-sm text-text-secondary">
              モデルの保存・比較にはログインが必要です
            </p>
            <button
              onClick={() => setShowAuth(true)}
              className="btn-primary px-6 py-2.5 rounded-lg text-sm cursor-pointer"
            >
              ログイン / 新規登録
            </button>
          </div>
        </div>
        <AuthModal isOpen={showAuth} onClose={() => setShowAuth(false)} />
      </>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <h1 className="font-mincho text-2xl font-bold text-glow-yellow text-accent">
          マイモデル
        </h1>
        <p className="text-sm text-text-secondary">
          保存したモデルを管理・比較できます
          <span className="text-text-muted ml-2">
            ({models.length}/{limit})
          </span>
        </p>
      </div>

      {/* Compare view or list */}
      {compareData ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          <CompareView
            data={compareData}
            onClose={() => setCompareData(null)}
          />
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {isLoading ? (
            <div className="glass-strong p-8 text-center">
              <div className="text-text-muted animate-pulse">読み込み中...</div>
            </div>
          ) : error ? (
            <div className="glass-strong p-6 text-center space-y-3">
              <div className="text-3xl">⚠️</div>
              <p className="text-sm text-text-secondary">{error}</p>
            </div>
          ) : (
            <>
              <ModelHistoryList
                models={models}
                selectedIds={selectedIds}
                onToggleSelect={handleToggleSelect}
                onDelete={handleDelete}
                onRename={handleRename}
              />

              {/* Spacer for sticky button */}
              {models.length > 0 && <div className="h-20" />}
            </>
          )}
        </motion.div>
      )}

      {/* Compare button (sticky bottom) */}
      {!compareData && models.length > 0 && (
        <CompareButton
          selectedCount={selectedIds.size}
          onClick={handleCompare}
          isLoading={comparing}
        />
      )}

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
