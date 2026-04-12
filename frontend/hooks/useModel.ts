"use client";

import { useState, useCallback } from "react";
import { fetchResults } from "@/lib/api";
import { getLastModelId } from "@/lib/storage";
import type { LearnResponse } from "@/lib/types";

export function useModel() {
  const [modelId, setModelId] = useState<string | null>(null);
  const [results, setResults] = useState<LearnResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadLastModel = useCallback(async () => {
    const id = getLastModelId();
    if (!id) return;

    setIsLoading(true);
    try {
      const data = await fetchResults(id);
      setModelId(id);
      setResults(data);
    } catch {
      // Model not found, that's ok
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    modelId,
    results,
    isLoading,
    setModelId,
    setResults,
    loadLastModel,
  };
}
