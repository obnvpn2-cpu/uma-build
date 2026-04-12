import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "特定商取引法に基づく表記 - UmaBuild",
};

export default function TokushohoPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <h1 className="font-mincho text-2xl font-bold text-accent text-glow-yellow">
        特定商取引法に基づく表記
      </h1>

      <div className="glass p-6 space-y-6 text-sm text-text-secondary leading-relaxed">
        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">販売業者</h2>
          <p>UmaBuild 運営事務局</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">運営責任者</h2>
          <p>請求があった場合には遅滞なく開示いたします</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">所在地</h2>
          <p>請求があった場合には遅滞なく開示いたします</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">お問い合わせ</h2>
          <p>メールにてお問い合わせください</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">販売価格</h2>
          <p>各プランの料金ページに記載の金額（税込）</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">支払方法</h2>
          <p>クレジットカード決済（Stripe経由）</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">支払時期</h2>
          <p>月額プラン：毎月の契約更新日に自動課金</p>
          <p>年額プラン：毎年の契約更新日に自動課金</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">サービス提供時期</h2>
          <p>決済完了後、即時ご利用いただけます</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">返品・キャンセルについて</h2>
          <p>
            デジタルサービスの性質上、購入後の返金はいたしかねます。
            サブスクリプションはいつでも解約可能で、解約後は次回更新日まで引き続きご利用いただけます。
          </p>
        </section>

        <section className="space-y-2 border-t border-white/10 pt-6">
          <h2 className="text-text-primary font-semibold">免責事項</h2>
          <p className="text-amber-400/90">
            本サービスは過去データに基づく統計的分析ツールであり、将来のレース結果を保証するものではありません。
            馬券の購入判断はご自身の責任で行ってください。
            本サービスの利用により生じた損害について、当社は一切の責任を負いません。
          </p>
        </section>
      </div>
    </div>
  );
}
