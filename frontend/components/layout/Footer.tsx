"use client";

export function Footer() {
  return (
    <footer className="border-t border-surface-border bg-surface-raised/50 mt-auto">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="text-xs text-text-muted space-y-2">
          <p className="font-bold text-text-secondary">免責事項</p>
          <p>
            本サービスは競馬の予測を行うものであり、的中を保証するものではありません。
            馬券の購入はご自身の判断と責任で行ってください。
            過去のデータに基づく分析結果は将来の結果を保証するものではありません。
          </p>
          <p>
            競馬はギャンブルです。必ず余裕資金の範囲内でお楽しみください。
          </p>
          <div className="pt-3 flex items-center justify-between">
            <span className="font-mincho text-text-secondary">
              UmaBuild
            </span>
            <span>&copy; {new Date().getFullYear()} UmaBuild</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
