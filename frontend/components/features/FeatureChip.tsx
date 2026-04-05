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
      className={`px-3 py-2.5 rounded-full text-sm cursor-pointer min-h-[44px] transition-all ${
        isSelected
          ? "text-surface font-bold border"
          : "glass-sm text-text-secondary hover:text-text-primary"
      }`}
      style={
        isSelected
          ? {
              background:
                "linear-gradient(135deg, #FFF373 0%, #F5E932 50%, #E0D020 100%)",
              borderColor: "rgba(245,233,50,0.6)",
              boxShadow:
                "0 0 18px rgba(245,233,50,0.45), inset 0 1px 0 rgba(255,255,255,0.4)",
            }
          : undefined
      }
    >
      {label}
    </motion.button>
  );
}
