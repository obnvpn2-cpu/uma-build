"use client";

import { useState, useCallback } from "react";
import { postLearn, pollJobStatus } from "@/lib/api";
import { getSessionId, setLastModelId, incrementDailyAttempts } from "@/lib/storage";
import type { LearnResponse } from "@/lib/types";

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 120; // 3s × 120 = 6 min max

export type StartLearningResult =
  | { ok: true; data: LearnResponse }
  | { ok: false; error: string };

export function useLearning() {
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<LearnResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const startLearning = useCallback(
    async (selectedFeatures: string[]): Promise<StartLearningResult> => {
      setIsLoading(true);
      setError(null);
      setResults(null);

      try {
        const sessionId = getSessionId();
        const { job_id } = await postLearn({
          selected_features: selectedFeatures,
          session_id: sessionId,
        });

        // Poll for results
        for (let i = 0; i < MAX_POLL_ATTEMPTS; i++) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          const status = await pollJobStatus(job_id);

          if (status.status === "completed") {
            const response = status.result!;
            setResults(response);
            if (response.model_id) {
              setLastModelId(response.model_id);
            }
            incrementDailyAttempts();
            return { ok: true, data: response };
          }
          if (status.status === "failed") {
            throw new Error(status.error || "学習に失敗しました");
          }
        }
        throw new Error("学習がタイムアウトしました");
      } catch (err) {
        const message = err instanceof Error ? err.message : "学習に失敗しました";
        setError(message);
        return { ok: false, error: message };
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const clearResults = useCallback(() => {
    setResults(null);
    setError(null);
  }, []);

  return {
    isLoading,
    results,
    error,
    startLearning,
    clearResults,
  };
}
