"use client";

import { useState, useEffect } from "react";
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

export function LearningProgress({ isLoading }: LearningProgressProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      setStepIndex(0);
      setProgress(0);
      return;
    }

    const stepInterval = setInterval(() => {
      setStepIndex((prev) => (prev < STEPS.length - 1 ? prev + 1 : prev));
    }, 5000);

    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + Math.random() * 3, 95));
    }, 200);

    return () => {
      clearInterval(stepInterval);
      clearInterval(progressInterval);
    };
  }, [isLoading]);

  if (!isLoading) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-surface-raised border border-surface-border rounded-xl p-6 space-y-4"
    >
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-text-secondary">{STEPS[stepIndex]}</span>
          <span className="text-accent font-mono">{Math.round(progress)}%</span>
        </div>
        <div className="w-full h-2 bg-surface-overlay rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-accent rounded-full"
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
              i <= stepIndex ? "bg-accent/60" : "bg-surface-border"
            }`}
          />
        ))}
      </div>
    </motion.div>
  );
}
