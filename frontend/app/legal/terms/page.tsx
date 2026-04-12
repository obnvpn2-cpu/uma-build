import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "利用規約 - UmaBuild",
};

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <h1 className="font-mincho text-2xl font-bold text-accent text-glow-yellow">
        利用規約
      </h1>

      <div className="glass p-6 space-y-6 text-sm text-text-secondary leading-relaxed">
        <p>
          この利用規約（以下「本規約」）は、UmaBuild（以下「本サービス」）の利用条件を定めるものです。
          ユーザーの皆さまには、本規約に同意いただいた上で本サービスをご利用いただきます。
        </p>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">第1条（適用）</h2>
          <p>
            本規約は、ユーザーと本サービス運営者との間の本サービスの利用に関わる一切の関係に適用されるものとします。
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">第2条（サービスの内容）</h2>
          <p>
            本サービスは、過去の競馬データに基づく統計的分析ツールを提供するものです。
            機械学習モデルの学習・バックテスト機能を通じて、ユーザーが独自の分析モデルを構築することを支援します。
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">第3条（禁止事項）</h2>
          <p>ユーザーは、以下の行為をしてはなりません。</p>
          <ul className="list-disc list-inside space-y-1 pl-2">
            <li>法令または公序良俗に違反する行為</li>
            <li>本サービスの運営を妨害する行為</li>
            <li>他のユーザーに不利益を与える行為</li>
            <li>本サービスのサーバーに過度な負荷をかける行為</li>
            <li>本サービスの情報を無断で商業利用する行為</li>
            <li>不正アクセスまたはこれを試みる行為</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">第4条（サービスの変更・停止）</h2>
          <p>
            運営者は、事前の通知なくサービスの内容を変更し、またはサービスの提供を停止もしくは中止することができるものとします。
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">第5条（知的財産権）</h2>
          <p>
            本サービスに関する知的財産権は、運営者に帰属します。
            ユーザーが本サービスを利用して生成した分析結果は、ユーザー自身の責任において利用できます。
          </p>
        </section>

        <section className="space-y-2 border-t border-white/10 pt-6">
          <h2 className="text-text-primary font-semibold">第6条（免責事項）</h2>
          <p className="text-amber-400/90">
            本サービスは過去データに基づく統計的分析ツールであり、将来のレース結果を保証するものではありません。
            本サービスが提供する分析結果、回収率、的中率等のデータは過去のバックテスト結果であり、
            将来の収益を約束するものではありません。
            馬券の購入判断はご自身の責任で行ってください。
            本サービスの利用により生じた損害について、運営者は一切の責任を負いません。
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">第7条（準拠法・管轄）</h2>
          <p>
            本規約の解釈にあたっては日本法を準拠法とし、
            紛争が生じた場合には東京地方裁判所を第一審の専属的合意管轄裁判所とします。
          </p>
        </section>

        <p className="text-text-muted text-xs pt-4">制定日：2026年4月12日</p>
      </div>
    </div>
  );
}
