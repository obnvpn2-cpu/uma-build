"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { AuthModal } from "@/components/auth/AuthModal";
import { LogOut, User, CreditCard } from "lucide-react";

export function Header() {
  const pathname = usePathname();
  const isLab = pathname === "/lab";
  const isPricing = pathname === "/pricing";
  const [showAuth, setShowAuth] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const { user, loading, signOut } = useAuth();

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-white/10 bg-black/30 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="font-mincho text-xl font-bold text-accent text-glow-yellow">
              UmaBuild
            </span>
            <span className="text-xs text-text-muted hidden sm:inline">
              ノーコード競馬予想AIビルダー
            </span>
          </Link>
          <nav className="flex items-center gap-3">
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

            {!loading && user ? (
              /* Logged in */
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="flex items-center gap-1.5 text-xs glass-sm px-2.5 py-1.5 rounded-full hover:bg-white/10 transition cursor-pointer"
                >
                  <User className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline max-w-[120px] truncate">
                    {user.email?.split("@")[0]}
                  </span>
                </button>

                {showMenu && (
                  <div className="absolute right-0 top-full mt-2 glass-strong p-1 rounded-lg min-w-[160px] shadow-xl">
                    <Link
                      href="/pricing"
                      onClick={() => setShowMenu(false)}
                      className="flex items-center gap-2 px-3 py-2 text-xs text-text-secondary hover:text-text-primary hover:bg-white/5 rounded transition"
                    >
                      <CreditCard className="w-3.5 h-3.5" />
                      プラン管理
                    </Link>
                    <button
                      onClick={() => { signOut(); setShowMenu(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-secondary hover:text-danger hover:bg-white/5 rounded transition cursor-pointer"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      ログアウト
                    </button>
                  </div>
                )}
              </div>
            ) : !loading ? (
              /* Logged out */
              <>
                <button
                  onClick={() => setShowAuth(true)}
                  className="text-xs text-text-secondary hover:text-text-primary transition cursor-pointer"
                >
                  ログイン
                </button>
                <Link
                  href="/pricing"
                  className={`text-xs font-bold px-3 py-1.5 rounded-full transition cursor-pointer ${
                    isPricing ? "btn-primary" : "btn-primary"
                  }`}
                >
                  Pro
                </Link>
              </>
            ) : null}
          </nav>
        </div>
      </header>

      <AuthModal isOpen={showAuth} onClose={() => setShowAuth(false)} />
    </>
  );
}
