"use client";

import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchFeatures, fetchDefaults } from "@/lib/api";
import { getSelectedFeatures, setSelectedFeatures } from "@/lib/storage";
import type { FeatureCategory } from "@/lib/types";

export function useFeatureSelection() {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [initialized, setInitialized] = useState(false);

  const {
    data: categories,
    isLoading: categoriesLoading,
    error: categoriesError,
  } = useQuery<FeatureCategory[]>({
    queryKey: ["features"],
    queryFn: fetchFeatures,
  });

  const { data: defaultsData } = useQuery({
    queryKey: ["feature-defaults"],
    queryFn: fetchDefaults,
  });

  // Initialize from localStorage or defaults
  useEffect(() => {
    if (initialized || !defaultsData) return;
    const stored = getSelectedFeatures();
    if (stored.length > 0) {
      setSelectedIds(new Set(stored));
    } else {
      setSelectedIds(new Set(defaultsData.default_features));
    }
    setInitialized(true);
  }, [defaultsData, initialized]);

  // Persist to localStorage
  useEffect(() => {
    if (!initialized) return;
    setSelectedFeatures(Array.from(selectedIds));
  }, [selectedIds, initialized]);

  const toggleFeature = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const toggleAll = useCallback(
    (_categoryId: string, featureIds: string[], selectAll: boolean) => {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const id of featureIds) {
          if (selectAll) {
            next.add(id);
          } else {
            next.delete(id);
          }
        }
        return next;
      });
    },
    []
  );

  const resetDefaults = useCallback(() => {
    if (defaultsData) {
      setSelectedIds(new Set(defaultsData.default_features));
    }
  }, [defaultsData]);

  return {
    categories: categories ?? [],
    selectedIds,
    isLoading: categoriesLoading,
    error: categoriesError,
    toggleFeature,
    toggleAll,
    resetDefaults,
  };
}
