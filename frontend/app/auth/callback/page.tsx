"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";

/**
 * OAuth / magic link callback landing page.
 *
 * Supabase JS handles two flows automatically when this page loads:
 * - PKCE flow: ?code=... is exchanged for a session
 * - Implicit flow: #access_token=... is parsed from the URL hash
 *
 * On success, we forward to the `next` query param (default /lab).
 * On failure, we surface Supabase's error_description so the user can
 * see what went wrong (most common: redirect URL not whitelisted in
 * Supabase Dashboard → Auth → URL Configuration).
 */
function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    // Check for OAuth provider errors in the hash (Supabase forwards
    // these from the IdP). Hash format: #error=...&error_description=...
    if (typeof window !== "undefined" && window.location.hash) {
      const hash = new URLSearchParams(window.location.hash.slice(1));
      const errDesc = hash.get("error_description");
      if (errDesc) {
        setErrorMsg(decodeURIComponent(errDesc.replace(/\+/g, " ")));
        return;
      }
    }

    // Subscribe to auth state. If supabase finishes processing the
    // code/hash and a session is established, navigate forward.
    const next = params.get("next") || "/lab";
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        router.replace(next);
      }
    });

    // Also poll once in case the session was already restored before
    // we subscribed (race condition on fast clients).
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) router.replace(next);
    });

    // If after 5s nothing happened and no error, show a generic
    // failure rather than leaving the user on a blank loading screen.
    const timeout = setTimeout(() => {
      setErrorMsg(
        "認証の完了に失敗しました。もう一度お試しいただくか、別の方法でログインしてください。",
      );
    }, 5000);

    return () => {
      sub.subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, [router, params]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="glass-strong w-full max-w-md p-6 text-center space-y-4">
        {errorMsg ? (
          <>
            <div className="text-3xl">⚠️</div>
            <h1 className="font-mincho text-lg font-bold">
              ログインに失敗しました
            </h1>
            <p className="text-xs text-danger break-words">{errorMsg}</p>
            <Link
              href="/lab"
              className="inline-block btn-primary px-6 py-2 rounded-lg text-sm"
            >
              トップへ戻る
            </Link>
          </>
        ) : (
          <>
            <div className="text-3xl animate-pulse">⏳</div>
            <p className="text-sm text-text-secondary">ログイン処理中...</p>
          </>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm text-text-secondary">読み込み中...</p>
      </div>
    }>
      <CallbackInner />
    </Suspense>
  );
}
