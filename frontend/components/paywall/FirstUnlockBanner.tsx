"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { sendEvent } from "@/lib/gtm";

export function FirstUnlockBanner() {
  useEffect(() => {
    sendEvent("first_unlock_granted");
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full rounded-lg p-4 text-center space-y-2"
      style={{
        background:
          "linear-gradient(135deg, rgba(88,166,255,0.15) 0%, rgba(245,233,50,0.15) 100%)",
        border: "1px solid rgba(88,166,255,0.3)",
      }}
    >
      <div className="flex items-center justify-center gap-2">
        <Sparkles className="w-5 h-5 text-accent" />
        <p className="text-sm font-semibold text-accent">
          初回限定！今回だけPro機能をすべて体験できます
        </p>
        <Sparkles className="w-5 h-5 text-accent" />
      </div>
      <p className="text-xs text-text-muted">
        次回からはProプラン限定になります
      </p>
      <a
        href="/pricing"
        onClick={() => sendEvent("first_unlock_upgrade_click")}
        className="btn-primary inline-block mt-2 px-5 py-2 rounded-lg text-sm cursor-pointer"
      >
        Proプランにアップグレード
      </a>
    </motion.div>
  );
}
