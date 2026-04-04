"use client";

import { getDailyAttempts } from "@/lib/storage";
import { useState, useEffect, useCallback } from "react";

const FREE_MAX = 5;
const PRO_MAX = 50;

export function useAttempts(isPro: boolean = false) {
  const [used, setUsed] = useState(0);
  const max = isPro ? PRO_MAX : FREE_MAX;

  useEffect(() => {
    setUsed(getDailyAttempts());
  }, []);

  const refresh = useCallback(() => {
    setUsed(getDailyAttempts());
  }, []);

  return {
    used,
    max,
    remaining: Math.max(0, max - used),
    isPro,
    refresh,
  };
}
