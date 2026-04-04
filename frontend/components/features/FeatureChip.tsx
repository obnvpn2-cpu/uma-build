"use client";

import { motion } from "framer-motion";

interface FeatureChipProps {
  id: string;
  label: string;
  description: string;
  isSelected: boolean;
  onToggle: (id: string) => void;
}

export function FeatureChip({ id, label, description, isSelected, onToggle }: FeatureChipProps) {
  return (
    <motion.button
      onClick={() => onToggle(id)}
      title={description}
      whileHover={{ y: -1, scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`px-3 py-2.5 rounded-full text-sm border cursor-pointer min-h-[44px] transition-colors ${
        isSelected
          ? "bg-accent/20 border-accent/50 text-accent shadow-[0_0_8px_rgba(88,166,255,0.15)]"
          : "bg-surface-overlay border-surface-border text-text-secondary hover:border-text-muted hover:text-text-primary hover:bg-surface-overlay/80"
      }`}
    >
      {label}
    </motion.button>
  );
}
