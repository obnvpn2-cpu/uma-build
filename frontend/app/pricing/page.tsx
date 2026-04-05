"use client";

import Link from "next/link";

const plans = [
  {
    name: "Free",
    price: "0",
    period: "",
    features: [
      "全特徴量 ON/OFF 可能",
      "2年分データ（クイック学習・30秒）",
      "1日5回まで学習可能",
      "バックテストサマリー表示",
      "条件別分析はぼかし表示",
      "実戦信頼度 最大★★",
      "未来予測ロック",
      "モデル保存 1個 / 90日",
    ],
    cta: "現在のプラン",
    ctaDisabled: true,
    highlight: false,
  },
  {
    name: "Pro",
    price: "1,480",
    period: "月額",
    yearlyPrice: "9,800円/年",
    features: [
      "全特徴量 ON/OFF + パラメータ調整",
      "5年分データ（フル学習・2-5分）",
      "月50回まで学習可能",
      "全詳細バックテスト",
      "条件別・年別・距離別の完全分析",
      "実戦信頼度 最大★★★★★",
      "全レース未来予測",
      "モデル保存 10個 / 無期限",
    ],
    cta: "近日公開",
    ctaDisabled: true,
    highlight: true,
  },
];

export default function PricingPage() {
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

      <div className="grid sm:grid-cols-2 gap-6">
        {plans.map((plan) => (
          <div
            key={plan.name}
            className={`p-6 space-y-4 relative ${
              plan.highlight ? "glass-strong" : "glass"
            }`}
            style={
              plan.highlight
                ? {
                    boxShadow:
                      "0 16px 48px rgba(0,0,0,0.55), 0 0 40px rgba(245,233,50,0.3)",
                  }
                : undefined
            }
          >
            {plan.highlight && (
              <span
                className="btn-primary absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-bold"
              >
                おすすめ
              </span>
            )}
            <div>
              <h2 className="font-mincho text-xl font-bold">{plan.name}</h2>
              <div className="flex items-baseline gap-1 mt-1">
                <span
                  className="text-3xl font-mono font-bold text-accent"
                  style={{
                    filter: "drop-shadow(0 0 12px rgba(245,233,50,0.5))",
                  }}
                >
                  {plan.price === "0" ? "無料" : `¥${plan.price}`}
                </span>
                {plan.period && (
                  <span className="text-text-muted text-sm">/ {plan.period}</span>
                )}
              </div>
              {plan.yearlyPrice && (
                <p className="text-xs text-text-muted mt-0.5">
                  年払い: {plan.yearlyPrice}
                </p>
              )}
            </div>
            <ul className="space-y-2">
              {plan.features.map((feature) => (
                <li
                  key={feature}
                  className="flex items-start gap-2 text-sm text-text-secondary"
                >
                  <span className="text-success mt-0.5 shrink-0">&#10003;</span>
                  {feature}
                </li>
              ))}
            </ul>
            <button
              disabled={plan.ctaDisabled}
              className={`w-full py-2 rounded-lg text-sm font-medium transition ${
                plan.highlight
                  ? "btn-primary"
                  : "glass-sm text-text-muted cursor-not-allowed"
              }`}
            >
              {plan.cta}
            </button>
          </div>
        ))}
      </div>

      <div className="text-center">
        <Link
          href="/lab"
          className="text-sm text-accent hover:underline"
        >
          ← AI Lab に戻る
        </Link>
      </div>

      <div className="text-xs text-text-muted text-center space-y-1 pt-4">
        <p>* Pro プランは開発中です。7日間の無料トライアル付き（クレカ必須）。</p>
        <p>
          本サービスの予測は的中を保証するものではありません。
          馬券購入はご自身の判断と責任で行ってください。
        </p>
      </div>
    </div>
  );
}
