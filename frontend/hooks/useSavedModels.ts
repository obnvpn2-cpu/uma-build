"use client";

import { useState, useEffect, useCallback } from "react";
import type { SavedModel } from "@/lib/types";
import {
  fetchSavedModels,
  saveModel as apiSaveModel,
  deleteModel as apiDeleteModel,
  renameModel as apiRenameModel,
} from "@/lib/api";

export function useSavedModels(enabled: boolean = true) {
  const [models, setModels] = useState<SavedModel[]>([]);
  const [limit, setLimit] = useState(3);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchSavedModels();
      setModels(data.models);
      setLimit(data.limit);
    } catch (e) {
      setError(e instanceof Error ? e.message : "モデル一覧の取得に失敗しました");
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const save = useCallback(
    async (modelId: string, name: string, featureIds: string[]) => {
      const result = await apiSaveModel(modelId, name, featureIds);
      await refresh();
      return result;
    },
    [refresh],
  );

  const remove = useCallback(
    async (modelId: string) => {
      await apiDeleteModel(modelId);
      await refresh();
    },
    [refresh],
  );

  const rename = useCallback(
    async (modelId: string, newName: string) => {
      await apiRenameModel(modelId, newName);
      await refresh();
    },
    [refresh],
  );

  return { models, limit, isLoading, error, save, remove, rename, refresh };
}
