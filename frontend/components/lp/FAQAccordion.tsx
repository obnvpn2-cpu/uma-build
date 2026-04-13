"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    q: "本当にコードを書かなくていいの？",
    a: "はい、一切不要です。特徴量をクリックで選んで「学習開始」を押すだけ。裏側でLightGBMが自動的にモデルを構築します。",
  },
  {
    q: "実際に馬券で勝てるの？",
    a: "UmaBuildは過去データに基づく統計分析ツールです。バックテストで高い回収率が出ても、将来の結果を保証するものではありません。馬券購入はご自身の判断と責任で行ってください。",
  },
  {
    q: "データはどこから取得している？",
    a: "JRA公式のレースデータを利用しています。過去数年分の全レース結果、馬体重、騎手成績など、包括的なデータセットで学習を行います。",
  },
  {
    q: "無料で使える？",
    a: "はい、Freeプランでは2年分のデータで1日5回まで学習を実行できます。まずは無料でお試しいただき、より高度な分析が必要な場合はProプランをご検討ください。",
  },
  {
    q: "AIの予測精度はどのくらい？",
    a: "精度は選択する特徴量やモデル設定によって異なります。バックテスト機能で過去データでの回収率・的中率を確認できるので、実際の数値をご自身の目で確かめてください。",
  },
];

export function FAQAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      {faqs.map((faq, i) => (
        <div key={i} className="glass overflow-hidden">
          <button
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
            className="w-full flex items-center justify-between p-6 text-left"
          >
            <span className="font-medium text-text-primary pr-4">
              {faq.q}
            </span>
            <ChevronDown
              className={`w-5 h-5 text-accent shrink-0 transition-transform duration-200 ${
                openIndex === i ? "rotate-180" : ""
              }`}
            />
          </button>
          <div
            className={`overflow-hidden transition-all duration-200 ${
              openIndex === i ? "max-h-40 opacity-100" : "max-h-0 opacity-0"
            }`}
          >
            <p className="px-6 pb-6 text-sm text-text-secondary leading-relaxed">
              {faq.a}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
