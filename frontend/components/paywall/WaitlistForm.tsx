"use client";

import { useState } from "react";
import { sendEvent } from "@/lib/gtm";

interface WaitlistFormProps {
  source: "pricing" | "lock_popup" | "blur_overlay";
}

export function WaitlistForm({ source }: WaitlistFormProps) {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || loading) return;

    setLoading(true);
    try {
      // Store in localStorage as lightweight collection
      // In production, this would POST to Supabase or Google Forms
      const existing = JSON.parse(
        localStorage.getItem("umabuild_waitlist") || "[]"
      );
      if (!existing.includes(email)) {
        existing.push(email);
        localStorage.setItem("umabuild_waitlist", JSON.stringify(existing));
      }

      sendEvent("waitlist_submit", { source });
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <p className="text-xs text-success text-center py-1">
        登録完了！Pro公開時にお知らせします。
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="email"
        placeholder="メールアドレス"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        className="flex-1 glass-sm px-3 py-1.5 rounded-lg text-xs bg-transparent border border-white/10 focus:border-accent/50 focus:outline-none transition min-w-0"
      />
      <button
        type="submit"
        disabled={loading}
        className="btn-primary px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap shrink-0"
      >
        {loading ? "..." : "通知を受取る"}
      </button>
    </form>
  );
}
