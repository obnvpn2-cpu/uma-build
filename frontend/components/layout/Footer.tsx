"use client";

import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-black/20 backdrop-blur-xl mt-auto">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="text-xs text-text-muted space-y-4">
          <p className="font-bold text-text-secondary">免責事項</p>
          <p className="text-amber-400/80">
            本サービスは過去データに基づく統計的分析ツールであり、将来のレース結果を保証するものではありません。
            馬券の購入はご自身の判断と責任で行ってください。
            過去のデータに基づく分析結果は将来の結果を保証するものではありません。
          </p>
          <p>競馬はギャンブルです。必ず余裕資金の範囲内でお楽しみください。</p>

          {/* Legal links */}
          <div className="flex flex-wrap gap-4 pt-2 border-t border-white/5">
            <Link
              href="/legal/tokushoho"
              className="hover:text-accent transition"
            >
              特定商取引法に基づく表記
            </Link>
            <Link href="/legal/terms" className="hover:text-accent transition">
              利用規約
            </Link>
            <Link
              href="/legal/privacy"
              className="hover:text-accent transition"
            >
              プライバシーポリシー
            </Link>
          </div>

          <div className="pt-3 flex items-center justify-between">
            <span className="font-mincho text-accent text-glow-yellow">
              UmaBuild
            </span>
            <span>&copy; {new Date().getFullYear()} UmaBuild</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
