"use client";

export function ProBadge() {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-xs font-bold rounded-full text-surface"
      style={{
        background:
          "linear-gradient(135deg, #FFF373 0%, #F5E932 50%, #E0D020 100%)",
        border: "1px solid rgba(245,233,50,0.6)",
        boxShadow:
          "0 0 12px rgba(245,233,50,0.5), inset 0 1px 0 rgba(255,255,255,0.4)",
      }}
    >
      Pro
    </span>
  );
}
