"use client";

import { fetchLimits } from "@/lib/api";
import { getSessionId } from "@/lib/storage";
import { useCallback, useEffect, useState } from "react";

interface UserLimits {
  isPro: boolean;
  max: number;
  used: number;
  remaining: number;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

const FREE_MAX = 5;

/**
 * Fetches the authoritative subscription state + daily usage from the
 * backend. Source of truth for "Pro vs Free" UI on pre-result screens.
 *
 * Falls back to {isPro:false, max:FREE_MAX} during the initial fetch and
 * on network error so the AI Lab is always operable.
 */
export function useUserLimits(): UserLimits {
  const [isPro, setIsPro] = useState(false);
  const [max, setMax] = useState(FREE_MAX);
  const [used, setUsed] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const sessionId = getSessionId();
      const data = await fetchLimits(sessionId);
      setIsPro(data.is_pro);
      setMax(data.max_attempts);
      setUsed(data.used_attempts);
    } catch {
      // Network/auth issue — keep last-known values, don't flip Pro→Free.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    isPro,
    max,
    used,
    remaining: Math.max(0, max - used),
    isLoading,
    refresh,
  };
}
