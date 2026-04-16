"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { sendEvent } from "@/lib/gtm";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Mode = "login" | "signup";

export function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);

  const { signInWithEmail, signUpWithEmail, signInWithGoogle } = useAuth();

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setMode("login");
      setEmail("");
      setPassword("");
      setError("");
      setLoading(false);
      setSignupSuccess(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "login") {
        const { error: err } = await signInWithEmail(email, password);
        if (err) {
          setError(err.message === "Invalid login credentials"
            ? "メールアドレスまたはパスワードが正しくありません"
            : err.message);
        } else {
          sendEvent("login", { method: "email" });
          onClose();
        }
      } else {
        const { error: err } = await signUpWithEmail(email, password);
        if (err) {
          setError(err.message);
        } else {
          sendEvent("signup", { method: "email" });
          setSignupSuccess(true);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError("");
    const { error: err } = await signInWithGoogle();
    if (err) {
      setError(err.message);
    } else {
      sendEvent(mode === "login" ? "login" : "signup", { method: "google" });
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass-strong w-full max-w-sm mx-4 p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-text-muted hover:text-text-primary transition cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="font-mincho text-xl font-bold text-center mb-6">
          {mode === "login" ? "ログイン" : "アカウント作成"}
        </h2>

        {signupSuccess ? (
          <div className="text-center space-y-4">
            <div className="text-3xl">📧</div>
            <p className="text-sm text-text-secondary">
              確認メールを送信しました。メール内のリンクをクリックして登録を完了してください。
            </p>
            <button
              onClick={() => { setSignupSuccess(false); setMode("login"); }}
              className="btn-primary px-6 py-2 rounded-lg text-sm cursor-pointer"
            >
              ログイン画面へ
            </button>
          </div>
        ) : (
          <>
            {/* Google OAuth */}
            <button
              onClick={handleGoogle}
              className="w-full glass-sm py-2.5 rounded-lg text-sm font-medium hover:bg-white/10 transition flex items-center justify-center gap-2 cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Googleで{mode === "login" ? "ログイン" : "登録"}
            </button>

            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 border-t border-white/10" />
              <span className="text-xs text-text-muted">または</span>
              <div className="flex-1 border-t border-white/10" />
            </div>

            {/* Email form */}
            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                type="email"
                placeholder="メールアドレス"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full glass-sm px-3 py-2 rounded-lg text-sm bg-transparent border border-white/10 focus:border-accent/50 focus:outline-none transition"
              />
              <input
                type="password"
                placeholder="パスワード（6文字以上）"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full glass-sm px-3 py-2 rounded-lg text-sm bg-transparent border border-white/10 focus:border-accent/50 focus:outline-none transition"
              />

              {error && (
                <p className="text-xs text-danger">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full btn-primary py-2.5 rounded-lg text-sm font-medium"
              >
                {loading
                  ? "処理中..."
                  : mode === "login"
                  ? "ログイン"
                  : "アカウント作成"}
              </button>
            </form>

            <p className="text-xs text-text-muted text-center mt-4">
              {mode === "login" ? (
                <>
                  アカウントをお持ちでない方は{" "}
                  <button
                    onClick={() => { setMode("signup"); setError(""); }}
                    className="text-accent hover:underline cursor-pointer"
                  >
                    新規登録
                  </button>
                </>
              ) : (
                <>
                  すでにアカウントをお持ちの方は{" "}
                  <button
                    onClick={() => { setMode("login"); setError(""); }}
                    className="text-accent hover:underline cursor-pointer"
                  >
                    ログイン
                  </button>
                </>
              )}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
