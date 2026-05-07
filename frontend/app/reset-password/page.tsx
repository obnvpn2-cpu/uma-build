"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/hooks/useAuth";

/**
 * Password reset landing page.
 *
 * Flow:
 *   1. User requests reset → email link with #access_token=...&type=recovery
 *   2. They click → land here → Supabase JS auto-restores a *temporary*
 *      session from the recovery token
 *   3. We let them set a new password via supabase.auth.updateUser()
 *   4. After success → redirect to /lab (now logged in)
 *
 * If they land here without a recovery token (direct visit), we show
 * a "request a new link" prompt instead of a broken form.
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const { updatePassword } = useAuth();

  const [hasRecoverySession, setHasRecoverySession] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    // Supabase JS parses the recovery token in the URL hash on load
    // and emits a PASSWORD_RECOVERY event. We confirm a session exists
    // before showing the form — otherwise the updateUser() call will
    // 401.
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY" || (event === "SIGNED_IN" && session)) {
        setHasRecoverySession(true);
      }
    });

    // Also check immediately in case the event fired before subscribe.
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setHasRecoverySession(true);
      } else if (typeof window !== "undefined" && !window.location.hash) {
        // No hash and no session → direct visit, no recovery in progress.
        setHasRecoverySession(false);
      }
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("パスワードは6文字以上で入力してください");
      return;
    }
    if (password !== confirm) {
      setError("確認用パスワードが一致しません");
      return;
    }
    setLoading(true);
    try {
      const { error: err } = await updatePassword(password);
      if (err) {
        setError(err.message);
      } else {
        setDone(true);
        // Brief pause so user reads the success message, then forward.
        setTimeout(() => router.replace("/lab"), 1500);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="glass-strong w-full max-w-md p-6">
        <h1 className="font-mincho text-xl font-bold text-center mb-6">
          新しいパスワードを設定
        </h1>

        {done ? (
          <div className="text-center space-y-4">
            <div className="text-3xl">✅</div>
            <p className="text-sm text-text-secondary">
              パスワードを更新しました。ラボに移動します...
            </p>
          </div>
        ) : hasRecoverySession === false ? (
          <div className="text-center space-y-4">
            <div className="text-3xl">⚠️</div>
            <p className="text-sm text-text-secondary">
              リセットリンクが無効か期限切れの可能性があります。<br />
              もう一度ログイン画面から「パスワードを忘れた方」を選んで再送信してください。
            </p>
            <Link
              href="/lab"
              className="inline-block btn-primary px-6 py-2 rounded-lg text-sm"
            >
              ログイン画面へ
            </Link>
          </div>
        ) : hasRecoverySession === null ? (
          <div className="text-center">
            <div className="text-3xl animate-pulse">⏳</div>
            <p className="text-sm text-text-secondary mt-3">確認中...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="password"
              placeholder="新しいパスワード（6文字以上）"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full glass-sm px-3 py-2 rounded-lg text-sm bg-transparent border border-white/10 focus:border-accent/50 focus:outline-none transition"
            />
            <input
              type="password"
              placeholder="確認のためもう一度"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              minLength={6}
              className="w-full glass-sm px-3 py-2 rounded-lg text-sm bg-transparent border border-white/10 focus:border-accent/50 focus:outline-none transition"
            />
            {error && <p className="text-xs text-danger">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-2.5 rounded-lg text-sm font-medium"
            >
              {loading ? "更新中..." : "パスワードを更新"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
