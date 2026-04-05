"use client";

import { motion } from "framer-motion";

interface QuickLearnButtonProps {
  selectedCount: number;
  isLoading: boolean;
  disabled: boolean;
  remainingAttempts: number;
  onClick: () => void;
}

export function QuickLearnButton({
  selectedCount,
  isLoading,
  disabled,
  remainingAttempts,
  onClick,
}: QuickLearnButtonProps) {
  const isActive = !disabled && !isLoading;
  return (
    <div className="flex flex-col items-center gap-3">
      <motion.button
        whileHover={!disabled ? { scale: 1.02 } : undefined}
        whileTap={!disabled ? { scale: 0.98 } : undefined}
        onClick={onClick}
        disabled={disabled || isLoading}
        className={`relative px-8 py-4 rounded-xl text-lg ${
          isActive ? "btn-primary pulse-glow" : "btn-primary"
        }`}
      >
        {isLoading ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            学習中...
          </span>
        ) : (
          "AI学習を開始"
        )}
      </motion.button>
      <p className="text-xs text-text-muted">
        {selectedCount}個の特徴量で学習 / 残り{remainingAttempts}回
      </p>
    </div>
  );
}
