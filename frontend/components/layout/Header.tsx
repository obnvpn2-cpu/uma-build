"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Header() {
  const pathname = usePathname();
  const isLab = pathname === "/lab" || pathname === "/";
  const isPricing = pathname === "/pricing";

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-black/30 backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/lab" className="flex items-center gap-2">
          <span className="font-mincho text-xl font-bold text-accent text-glow-yellow">
            UmaBuild
          </span>
          <span className="text-xs text-text-muted hidden sm:inline">
            ノーコード競馬予想AIビルダー
          </span>
        </Link>
        <nav className="flex items-center gap-4">
          <Link
            href="/lab"
            className={`text-sm transition relative py-1 ${
              isLab
                ? "text-text-primary font-medium"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            AI Lab
            {isLab && (
              <span
                className="absolute -bottom-[17px] left-0 right-0 h-0.5 rounded-full bg-accent"
                style={{ boxShadow: "0 0 12px rgba(245,233,50,0.6)" }}
              />
            )}
          </Link>
          <Link
            href="/pricing"
            className={`text-xs font-bold px-3 py-1.5 rounded-full transition cursor-pointer ${
              isPricing ? "btn-primary" : "btn-primary"
            }`}
          >
            Pro
          </Link>
        </nav>
      </div>
    </header>
  );
}
