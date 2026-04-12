"use client";

import Link from "next/link";

interface ProLockSectionProps {
  title: string;
}

export function ProLockSection({ title }: ProLockSectionProps) {
  return (
    <div className="glass p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/40">
          Pro 限定
        </span>
      </div>
      <div className="flex flex-col items-center justify-center py-8 space-y-3 text-center">
        <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center">
          <svg
            className="w-6 h-6 text-text-muted"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>
        <p className="text-sm text-text-secondary">
          Proプランで詳細データを確認できます
        </p>
        <Link
          href="/pricing"
          className="btn-primary px-5 py-2 rounded-lg text-sm inline-block"
        >
          Pro で見る
        </Link>
      </div>
    </div>
  );
}
