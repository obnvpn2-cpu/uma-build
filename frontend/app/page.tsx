import Link from "next/link";
import {
  MousePointerClick,
  Brain,
  BarChart3,
  Check,
  X,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import { FAQAccordion } from "@/components/lp/FAQAccordion";

/* ── JSON-LD structured data ── */
const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "UmaBuild",
  applicationCategory: "UtilitiesApplication",
  operatingSystem: "Web",
  offers: [
    { "@type": "Offer", price: "0", priceCurrency: "JPY" },
    { "@type": "Offer", price: "1480", priceCurrency: "JPY" },
  ],
  description:
    "競馬の予想AIをプログラミングなしで作れるWebサービス。81の特徴量から選ぶだけで、LightGBMモデルを自動学習し、バックテストで回収率を即確認。",
  url: "https://uma-build.vercel.app",
};

/* ── Static data ── */
const steps = [
  {
    num: 1,
    icon: MousePointerClick,
    title: "特徴量を選ぶ",
    desc: "距離・馬体重・騎手成績など81項目からクリックで選択",
  },
  {
    num: 2,
    icon: Brain,
    title: "AIが学習",
    desc: "LightGBMが過去のレースデータを自動分析",
  },
  {
    num: 3,
    icon: BarChart3,
    title: "回収率を確認",
    desc: "バックテスト結果で回収率・的中率をすぐ確認",
  },
];

const yearlyData = [
  { year: "2022", roi: 72 },
  { year: "2023", roi: 95 },
  { year: "2024", roi: 87 },
];

const featureImportance = [
  { name: "前走着順", pct: 92 },
  { name: "騎手勝率", pct: 78 },
  { name: "馬体重変化", pct: 65 },
  { name: "距離適性", pct: 58 },
  { name: "斤量", pct: 42 },
];

const comparisonRows = [
  { label: "コード不要", uma: true, site: true, diy: false },
  { label: "カスタマイズ性", uma: "◎", site: "×", diy: "◎" },
  { label: "根拠の透明性", uma: "◎", site: "×", diy: "◎" },
  { label: "コスト", uma: "¥0〜", site: "¥数千/月", diy: "¥0" },
  { label: "所要時間", uma: "3分", site: "—", diy: "数十時間" },
];

/* ── Page Component ── */
export default function LandingPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* ━━ Hero ━━ */}
      <section className="relative min-h-[calc(100vh-3.5rem)] flex items-center overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-accent/[0.06] rounded-full blur-[120px] pointer-events-none" />

        <div className="max-w-6xl mx-auto px-4 py-20 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center relative">
          <div className="space-y-8">
            <h1 className="font-mincho text-4xl sm:text-5xl lg:text-[3.5rem] font-bold leading-[1.2] tracking-tight">
              予想を買うのをやめて、
              <br />
              <span className="text-accent text-glow-yellow">
                AIに作らせよう。
              </span>
            </h1>
            <p className="text-lg sm:text-xl text-text-secondary max-w-lg leading-relaxed">
              81の特徴量から選ぶだけ。
              <br className="hidden sm:block" />
              あなただけの競馬AIが、
              <span className="text-text-primary font-medium">3分</span>
              で完成する。
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link
                href="/lab"
                className="btn-primary pulse-glow inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-lg text-lg font-bold"
              >
                無料でAIを作る
                <ArrowRight className="w-5 h-5" strokeWidth={1.5} />
              </Link>
            </div>
            <p className="text-xs text-text-muted">
              登録不要・クレジットカード不要
            </p>
          </div>

          {/* Mock UI visual */}
          <div className="relative hidden lg:block">
            <div className="absolute -inset-10 bg-accent/5 rounded-full blur-3xl" />
            <div className="glass-strong p-6 relative border-t border-l border-white/[0.08]">
              {/* Window chrome */}
              <div className="flex items-center gap-2 mb-5">
                <div className="w-2.5 h-2.5 rounded-full bg-danger/80" />
                <div className="w-2.5 h-2.5 rounded-full bg-warning/80" />
                <div className="w-2.5 h-2.5 rounded-full bg-success/80" />
                <span className="text-[11px] text-text-muted ml-2 font-mono">
                  UmaBuild AI Lab
                </span>
              </div>

              {/* Step indicator */}
              <div className="flex items-center gap-3 mb-4">
                <span className="w-6 h-6 rounded-full bg-accent text-surface text-xs font-bold flex items-center justify-center">
                  1
                </span>
                <div className="h-0.5 flex-1 bg-accent/30 rounded" />
                <span className="w-6 h-6 rounded-full bg-white/10 text-text-muted text-xs font-bold flex items-center justify-center">
                  2
                </span>
                <div className="h-0.5 flex-1 bg-white/10 rounded" />
                <span className="w-6 h-6 rounded-full bg-white/10 text-text-muted text-xs font-bold flex items-center justify-center">
                  3
                </span>
              </div>

              <p className="text-xs text-text-secondary mb-3 font-medium">
                特徴量を選択してください
              </p>

              {/* Feature chips */}
              <div className="flex flex-wrap gap-2 mb-5">
                {["距離", "馬体重", "騎手勝率", "前走着順", "斤量"].map(
                  (f) => (
                    <span
                      key={f}
                      className="px-3 py-1 text-xs rounded-full bg-accent/20 text-accent border border-accent/30 font-medium inline-flex items-center gap-1"
                    >
                      <Check className="w-3 h-3" strokeWidth={2} />
                      {f}
                    </span>
                  )
                )}
                {["枠番", "馬齢", "調教師"].map((f) => (
                  <span
                    key={f}
                    className="px-3 py-1 text-xs rounded-full bg-white/[0.04] border border-white/10 text-text-muted"
                  >
                    {f}
                  </span>
                ))}
              </div>

              {/* CTA */}
              <div className="btn-primary w-full py-2.5 rounded-lg text-sm text-center font-bold">
                学習を開始する →
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ━━ 3 Steps ━━ */}
      <section className="py-24 sm:py-32">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="font-mincho text-3xl sm:text-4xl font-bold text-center mb-4">
            たった
            <span className="text-accent text-glow-yellow">3ステップ</span>
            で、
            <br className="sm:hidden" />
            あなただけのAIが完成
          </h2>
          <p className="text-text-secondary text-center mb-14 max-w-lg mx-auto">
            専門知識は不要。クリック操作だけで、本格的な競馬AIを構築できます。
          </p>

          <div className="grid sm:grid-cols-3 gap-6">
            {steps.map((s) => (
              <div
                key={s.num}
                className="glass glass-hover p-8 text-center space-y-4"
              >
                <div className="mx-auto w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center">
                  <s.icon className="w-7 h-7 text-accent" strokeWidth={1.5} />
                </div>
                <div className="text-xs font-mono text-accent font-medium tracking-[0.1em]">
                  STEP {s.num}
                </div>
                <h3 className="font-mincho text-xl font-bold">{s.title}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ━━ Demo Results ━━ */}
      <section className="py-24 sm:py-32">
        <div className="max-w-5xl mx-auto px-4">
          <div className="grid lg:grid-cols-[2fr_3fr] gap-10 lg:gap-14 items-start">
            {/* Left column — heading + key stats */}
            <div className="space-y-8">
              <div>
                <p className="text-xs font-mono text-accent font-medium tracking-[0.1em] mb-4">
                  BACKTEST RESULTS
                </p>
                <h2 className="font-mincho text-3xl sm:text-4xl font-bold leading-snug">
                  こんな分析結果が、
                  <span className="text-accent text-glow-yellow">ワンクリック</span>
                  で。
                </h2>
                <p className="text-text-secondary mt-4">
                  バックテストで過去レースの回収率を即座に算出します。
                </p>
              </div>

              {/* Key metrics stacked */}
              <div className="space-y-6">
                <div>
                  <p className="text-xs text-text-muted tracking-[0.1em] mb-1">回収率</p>
                  <p
                    className="text-4xl sm:text-5xl font-mono font-bold text-accent"
                    style={{ filter: "drop-shadow(0 0 12px rgba(245,233,50,0.5))" }}
                  >
                    87.3%
                  </p>
                </div>
                <div className="flex gap-8">
                  <div>
                    <p className="text-xs text-text-muted tracking-[0.1em] mb-1">的中率</p>
                    <p className="text-2xl font-mono font-bold text-text-primary">18.2%</p>
                  </div>
                  <div>
                    <p className="text-xs text-text-muted tracking-[0.1em] mb-1">分析レース数</p>
                    <p className="text-2xl font-mono font-bold text-text-primary">1,248</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right column — charts */}
            <div className="space-y-6">
              {/* Yearly ROI */}
              <div className="glass p-8 sm:p-10">
                <p className="text-sm text-text-secondary mb-5 font-medium flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-accent" strokeWidth={1.5} />
                  年別 ROI
                </p>
                <div className="space-y-3">
                  {yearlyData.map(({ year, roi }) => (
                    <div key={year} className="flex items-center gap-3" role="img" aria-label={`${year}年のROI: ${roi}%`}>
                      <span className="text-xs font-mono text-text-muted w-10">
                        {year}
                      </span>
                      <div className="flex-1 h-6 rounded bg-white/5 overflow-hidden">
                        <div
                          className="h-full rounded bg-gradient-to-r from-accent-dark to-accent"
                          style={{ width: `${roi}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-accent w-10 text-right">
                        {roi}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Feature importance */}
              <div className="glass p-8 sm:p-10">
                <p className="text-sm text-text-secondary mb-5 font-medium">
                  特徴量重要度 TOP 5
                </p>
                <div className="space-y-3">
                  {featureImportance.map(({ name, pct }) => (
                    <div key={name} className="flex items-center gap-3" role="img" aria-label={`${name}: 重要度${pct}%`}>
                      <span className="text-xs text-text-secondary w-20 truncate">
                        {name}
                      </span>
                      <div className="flex-1 h-4 rounded-full bg-white/5 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-accent/50"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <p className="text-xs text-text-muted text-center mt-8">
            ※ 過去データに基づくバックテスト結果であり、将来の収益を保証するものではありません
          </p>
        </div>
      </section>

      {/* ━━ Comparison ━━ */}
      <section className="py-24 sm:py-32">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="font-mincho text-3xl sm:text-4xl font-bold text-center mb-14">
            なぜ
            <span className="text-accent text-glow-yellow">UmaBuild</span>
            なのか
          </h2>

          <div className="glass overflow-hidden overflow-x-auto">
            <table className="w-full text-sm min-w-[480px]">
              <thead>
                <tr className="bg-white/[0.04]">
                  <th scope="col" className="text-left py-4 px-5 text-text-muted font-normal" />
                  <th scope="col" className="py-4 px-5 text-center">
                    <span className="text-accent font-bold font-mincho text-base">
                      UmaBuild
                    </span>
                  </th>
                  <th scope="col" className="py-4 px-5 text-center text-text-secondary font-normal">
                    予想サイト購入
                  </th>
                  <th scope="col" className="py-4 px-5 text-center text-text-secondary font-normal">
                    自力コーディング
                  </th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row, idx) => (
                  <tr
                    key={row.label}
                    className={`hover:bg-white/[0.02] transition-colors ${
                      idx % 2 === 1 ? "bg-white/[0.02]" : ""
                    }`}
                  >
                    <th scope="row" className="py-3.5 px-5 text-left text-text-secondary font-medium">
                      {row.label}
                    </th>
                    {(
                      [row.uma, row.site, row.diy] as (string | boolean)[]
                    ).map((val, i) => (
                      <td key={i} className="py-3.5 px-5 text-center">
                        {typeof val === "boolean" ? (
                          val ? (
                            <Check className="w-5 h-5 text-success mx-auto" strokeWidth={1.5} aria-label="対応" />
                          ) : (
                            <X className="w-5 h-5 text-danger/70 mx-auto" strokeWidth={1.5} aria-label="非対応" />
                          )
                        ) : (
                          <span
                            className={
                              i === 0
                                ? "text-accent font-bold"
                                : "text-text-muted"
                            }
                          >
                            {val}
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ━━ FAQ ━━ */}
      <section className="py-24 sm:py-32">
        <div className="max-w-3xl mx-auto px-4">
          <h2 className="font-mincho text-3xl sm:text-4xl font-bold text-center mb-14">
            よくある質問
          </h2>
          <FAQAccordion />
        </div>
      </section>

      {/* ━━ Pricing preview ━━ */}
      <section className="py-24 sm:py-32">
        <div className="max-w-3xl mx-auto px-4">
          <h2 className="font-mincho text-3xl sm:text-4xl font-bold text-center mb-4">
            シンプルな料金体系
          </h2>
          <p className="text-text-secondary text-center mb-14">
            まずは無料で始めて、必要に応じてアップグレード
          </p>

          <div className="grid sm:grid-cols-2 gap-6">
            {/* Free */}
            <div className="glass p-8 space-y-5">
              <div>
                <h3 className="font-mincho text-xl font-bold">Free</h3>
                <p className="text-3xl font-mono font-bold text-accent mt-2">
                  無料
                </p>
              </div>
              <ul className="space-y-2.5 text-sm text-text-secondary">
                {[
                  "2年分データで学習",
                  "1日5回まで学習",
                  "全特徴量 ON/OFF 可能",
                  "バックテストサマリー表示",
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="w-4 h-4 text-success mt-0.5 shrink-0" strokeWidth={1.5} />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href="/lab"
                className="block w-full text-center glass-sm py-2.5 rounded-lg text-sm font-medium text-text-primary hover:bg-white/[0.06] transition"
              >
                今すぐ始める
              </Link>
            </div>

            {/* Pro */}
            <div
              className="glass-strong p-8 space-y-5 relative"
              style={{
                boxShadow:
                  "0 16px 48px rgba(0,0,0,0.55), 0 0 40px rgba(245,233,50,0.2)",
              }}
            >
              <span className="btn-primary absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-bold whitespace-nowrap">
                おすすめ
              </span>
              <div>
                <h3 className="font-mincho text-xl font-bold">Pro</h3>
                <div className="flex items-baseline gap-1 mt-2">
                  <span
                    className="text-3xl font-mono font-bold text-accent"
                    style={{
                      filter: "drop-shadow(0 0 12px rgba(245,233,50,0.5))",
                    }}
                  >
                    ¥1,480
                  </span>
                  <span className="text-text-muted text-sm">/ 月</span>
                </div>
              </div>
              <ul className="space-y-2.5 text-sm text-text-secondary">
                {[
                  "5年分データでフル学習",
                  "月50回まで学習",
                  "全特徴量 + パラメータ調整",
                  "全詳細バックテスト",
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <Check className="w-4 h-4 text-success mt-0.5 shrink-0" strokeWidth={1.5} />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                disabled
                className="btn-primary w-full py-2.5 rounded-lg text-sm font-bold"
              >
                近日公開
              </button>
            </div>
          </div>

          <div className="text-center mt-8">
            <Link
              href="/pricing"
              className="text-sm text-accent hover:underline inline-flex items-center gap-1"
            >
              料金の詳細を見る
              <ArrowRight className="w-3 h-3" strokeWidth={1.5} />
            </Link>
          </div>
        </div>
      </section>

      {/* ━━ Final CTA ━━ */}
      <section className="py-24 sm:py-32 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-accent/[0.03] to-transparent pointer-events-none" />
        <div className="max-w-3xl mx-auto px-4 text-center relative space-y-8">
          <h2 className="font-mincho text-3xl sm:text-4xl font-bold leading-snug">
            今日から、あなたの
            <br />
            <span className="text-accent text-glow-yellow">予想AI</span>
            を作り始めよう。
          </h2>
          <p className="text-text-secondary text-lg">
            登録不要、完全無料で今すぐ始められます。
          </p>
          <Link
            href="/lab"
            className="btn-primary pulse-glow inline-flex items-center gap-2 px-8 py-3.5 rounded-lg text-lg font-bold"
          >
            無料でAIを作る
            <ArrowRight className="w-5 h-5" strokeWidth={1.5} />
          </Link>
        </div>
      </section>
    </>
  );
}
