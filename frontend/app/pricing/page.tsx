"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { sendEvent } from "@/lib/gtm";
import { useAuth } from "@/hooks/useAuth";
import { AuthModal } from "@/components/auth/AuthModal";
import { WaitlistForm } from "@/components/paywall/WaitlistForm";
import { API_BASE } from "@/lib/api";

type BillingCycle = "monthly" | "yearly";

const features = {
  free: [
    "全特徴量 ON/OFF 可能",
    "2年分データ（クイック学習・30秒）",
    "1日5回まで学習可能",
    "バックテストサマリー表示",
    "条件別分析はぼかし表示",
    "実戦信頼度 最大★★",
    "未来予測ロック",
    "モデル保存 1個 / 90日",
  ],
  pro: [
    "全特徴量 ON/OFF + パラメータ調整",
    "5年分データ（フル学習・2-5分）",
    "月50回まで学習可能",
    "全詳細バックテスト",
    "条件別・年別・距離別の完全分析",
    "実戦信頼度 最大★★★★★",
    "全レース未来予測",
    "モデル保存 10個 / 無期限",
  ],
};

export default function PricingPage() {
  const [cycle, setCycle] = useState<BillingCycle>("yearly");
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");
  const [showAuth, setShowAuth] = useState(false);
  const { user, session } = useAuth();

  useEffect(() => {
    sendEvent("pricing_view");
  }, []);

  const handleCheckout = useCallback(async () => {
    if (!session) {
      setShowAuth(true);
      return;
    }

    setCheckoutLoading(true);
    setCheckoutError("");
    try {
      const res = await fetch(`${API_BASE}/api/stripe/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ plan: cycle }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setCheckoutError(body.detail || "チェックアウトの開始に失敗しました");
        return;
      }
      const data = await res.json();
      if (data.checkout_url) {
        sendEvent("checkout_start", { plan: cycle });
        window.location.href = data.checkout_url;
      }
    } catch {
      setCheckoutError("ネットワークエラーが発生しました。再度お試しください。");
    } finally {
      setCheckoutLoading(false);
    }
  }, [session, cycle]);

  const handlePortal = useCallback(async () => {
    if (!session) return;
    try {
      const res = await fetch(`${API_BASE}/api/stripe/portal`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
      });
      const data = await res.json();
      if (data.portal_url) {
        window.location.href = data.portal_url;
      }
    } catch {
      // Error handled silently
    }
  }, [session]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
      <div className="text-center space-y-2">
        <h1 className="font-mincho text-3xl font-bold text-accent text-glow-yellow">
          料金プラン
        </h1>
        <p className="text-text-secondary">
          あなただけの競馬AIを、もっと強力に
        </p>
      </div>

      {/* Billing cycle toggle */}
      <div className="flex justify-center">
        <div className="glass-sm inline-flex rounded-full p-0.5">
          <button
            onClick={() => setCycle("monthly")}
            className={`px-4 py-1.5 rounded-full text-xs font-medium transition cursor-pointer ${
              cycle === "monthly"
                ? "bg-accent/20 text-accent"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            月額
          </button>
          <button
            onClick={() => setCycle("yearly")}
            className={`px-4 py-1.5 rounded-full text-xs font-medium transition cursor-pointer ${
              cycle === "yearly"
                ? "bg-accent/20 text-accent"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            年額
            <span className="ml-1 text-success">45%OFF</span>
          </button>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-6">
        {/* Free plan */}
        <div className="glass p-6 space-y-4">
          <div>
            <h2 className="font-mincho text-xl font-bold">Free</h2>
            <div className="flex items-baseline gap-1 mt-1">
              <span
                className="text-3xl font-mono font-bold text-accent"
                style={{ filter: "drop-shadow(0 0 12px rgba(245,233,50,0.5))" }}
              >
                無料
              </span>
            </div>
          </div>
          <ul className="space-y-2">
            {features.free.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="text-success mt-0.5 shrink-0">&#10003;</span>
                {f}
              </li>
            ))}
          </ul>
          <button
            disabled
            className="w-full py-2 rounded-lg text-sm font-medium glass-sm text-text-muted cursor-not-allowed"
          >
            現在のプラン
          </button>
        </div>

        {/* Pro plan */}
        <div
          className="glass-strong p-6 space-y-4 relative"
          style={{
            boxShadow: "0 16px 48px rgba(0,0,0,0.55), 0 0 40px rgba(245,233,50,0.3)",
          }}
        >
          <span className="btn-primary absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-bold">
            おすすめ
          </span>
          <div>
            <h2 className="font-mincho text-xl font-bold">Pro</h2>
            <div className="flex items-baseline gap-1 mt-1">
              <span
                className="text-3xl font-mono font-bold text-accent"
                style={{ filter: "drop-shadow(0 0 12px rgba(245,233,50,0.5))" }}
              >
                {cycle === "monthly" ? "¥1,480" : "¥9,800"}
              </span>
              <span className="text-text-muted text-sm">
                / {cycle === "monthly" ? "月額" : "年額"}
              </span>
            </div>
            {cycle === "monthly" && (
              <p className="text-xs text-text-muted mt-0.5">
                年払い: ¥9,800/年（¥817/月相当）
              </p>
            )}
            {cycle === "yearly" && (
              <p className="text-xs text-text-muted mt-0.5">
                月あたり ¥817（月額より45%おトク）
              </p>
            )}
          </div>
          <ul className="space-y-2">
            {features.pro.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="text-success mt-0.5 shrink-0">&#10003;</span>
                {f}
              </li>
            ))}
          </ul>

          <button
            onClick={handleCheckout}
            disabled={checkoutLoading}
            className="w-full btn-primary py-2.5 rounded-lg text-sm font-medium cursor-pointer"
          >
            {checkoutLoading
              ? "処理中..."
              : "7日間無料でProを始める"}
          </button>

          {checkoutError && (
            <p className="text-xs text-danger text-center">{checkoutError}</p>
          )}

          <p className="text-[10px] text-text-muted text-center">
            7日間無料トライアル付き・いつでも解約可
          </p>

          {/* Waitlist fallback (shown when user not logged in and Stripe not yet live) */}
          {!user && (
            <div className="pt-2 border-t border-white/10">
              <p className="text-xs text-text-muted text-center mb-2">
                Pro公開時に通知を受け取る
              </p>
              <WaitlistForm source="pricing" />
            </div>
          )}
        </div>
      </div>

      {/* Plan management for existing subscribers */}
      {user && (
        <div className="text-center">
          <button
            onClick={handlePortal}
            className="text-xs text-text-secondary hover:text-accent transition cursor-pointer"
          >
            サブスクリプション管理（解約・カード変更）
          </button>
        </div>
      )}

      <div className="text-center">
        <Link href="/lab" className="text-sm text-accent hover:underline">
          ← AI Lab に戻る
        </Link>
      </div>

      <div className="text-xs text-text-muted text-center space-y-1 pt-4">
        <p>* 7日間の無料トライアル付き（クレジットカード必須）。1レース分の馬券代で月50回のAI分析。</p>
        <p>
          本サービスの予測は的中を保証するものではありません。
          馬券購入はご自身の判断と責任で行ってください。
        </p>
      </div>

      <AuthModal isOpen={showAuth} onClose={() => setShowAuth(false)} />
    </div>
  );
}
