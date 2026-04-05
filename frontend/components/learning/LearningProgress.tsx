"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";

interface LearningProgressProps {
  isLoading: boolean;
}

const STEPS = [
  "データ読み込み中...",
  "特徴量を構築中...",
  "LightGBMで学習中...",
  "バックテスト実行中...",
  "結果を集計中...",
];

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}分${s}秒`;
}

export function LearningProgress({ isLoading }: LearningProgressProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isLoading) {
      setStepIndex(0);
      setProgress(0);
      setElapsedSec(0);
      startTimeRef.current = null;
      return;
    }

    startTimeRef.current = Date.now();

    const stepInterval = setInterval(() => {
      setStepIndex((prev) => (prev < STEPS.length - 1 ? prev + 1 : prev));
    }, 5000);

    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + Math.random() * 3, 95));
    }, 200);

    const elapsedInterval = setInterval(() => {
      if (startTimeRef.current) {
        setElapsedSec(
          Math.floor((Date.now() - startTimeRef.current) / 1000)
        );
      }
    }, 1000);

    return () => {
      clearInterval(stepInterval);
      clearInterval(progressInterval);
      clearInterval(elapsedInterval);
    };
  }, [isLoading]);

  if (!isLoading) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass p-6 space-y-4"
    >
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-text-secondary">{STEPS[stepIndex]}</span>
          <span className="text-accent font-mono font-bold">
            {Math.round(progress)}%
          </span>
        </div>
        <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{
              background:
                "linear-gradient(90deg, #FFF373 0%, #F5E932 50%, #E0D020 100%)",
              boxShadow: "0 0 12px rgba(245,233,50,0.55)",
            }}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>
      <div className="flex gap-2">
        {STEPS.map((step, i) => (
          <div
            key={step}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= stepIndex ? "bg-accent/70" : "bg-white/10"
            }`}
          />
        ))}
      </div>
      <div className="flex items-center justify-between text-xs pt-1">
        <span className="text-text-muted">
          <span className="font-mono text-accent">{formatElapsed(elapsedSec)}</span>{" "}
          経過
        </span>
        <span className="text-text-muted">目安: 3〜5分</span>
      </div>
      <div className="mt-2 p-3 glass-sm">
        <p className="text-xs text-text-secondary leading-relaxed">
          別タブで他の作業をしていても大丈夫です。
          <br />
          <span className="text-accent font-semibold">このタブは閉じずに</span>
          お待ちください。
        </p>
      </div>
    </motion.div>
  );
}
