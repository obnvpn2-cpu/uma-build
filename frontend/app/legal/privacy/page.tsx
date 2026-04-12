import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "プライバシーポリシー - UmaBuild",
};

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <h1 className="font-mincho text-2xl font-bold text-accent text-glow-yellow">
        プライバシーポリシー
      </h1>

      <div className="glass p-6 space-y-6 text-sm text-text-secondary leading-relaxed">
        <p>
          UmaBuild（以下「本サービス」）は、ユーザーの個人情報の保護を重要と考え、
          以下の方針に基づき個人情報の取り扱いを行います。
        </p>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">1. 収集する情報</h2>
          <ul className="list-disc list-inside space-y-1 pl-2">
            <li>メールアドレス（アカウント登録時）</li>
            <li>決済情報（Stripe経由、当社では保持しません）</li>
            <li>サービス利用ログ（学習実行回数、選択した特徴量等）</li>
            <li>アクセスログ（IPアドレス、ブラウザ情報等）</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">2. 利用目的</h2>
          <ul className="list-disc list-inside space-y-1 pl-2">
            <li>本サービスの提供・運営</li>
            <li>ユーザーからのお問い合わせへの対応</li>
            <li>サービス改善のための分析</li>
            <li>利用規約に違反する行為への対応</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">3. 第三者提供</h2>
          <p>
            法令に基づく場合を除き、ユーザーの同意なく個人情報を第三者に提供することはありません。
            ただし、以下のサービスを利用しており、それぞれのプライバシーポリシーに従います。
          </p>
          <ul className="list-disc list-inside space-y-1 pl-2">
            <li>Stripe（決済処理）</li>
            <li>Vercel（ホスティング）</li>
            <li>Sentry（エラー追跡）</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">4. Cookie・アクセス解析</h2>
          <p>
            本サービスでは、サービス改善のためにCookieおよびアクセス解析ツールを使用する場合があります。
            ブラウザの設定によりCookieを無効にすることができますが、一部の機能が利用できなくなる場合があります。
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">5. 安全管理</h2>
          <p>
            個人情報の漏洩、紛失、毀損等を防止するために、適切な安全管理措置を講じます。
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-text-primary font-semibold">6. ポリシーの変更</h2>
          <p>
            本ポリシーの内容は、法令等の変更やサービスの変更に伴い、事前の通知なく変更することがあります。
            変更後のプライバシーポリシーは、本ページに掲載した時点から効力を生じるものとします。
          </p>
        </section>

        <p className="text-text-muted text-xs pt-4">制定日：2026年4月12日</p>
      </div>
    </div>
  );
}
