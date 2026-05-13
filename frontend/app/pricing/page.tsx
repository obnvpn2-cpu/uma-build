import type { Metadata } from "next";
import { PricingClient } from "./PricingClient";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "料金プラン — 月額¥1,480で月50回のAI分析",
  description:
    "Free (1日5回・2年分データ) と Pro (月¥1,480・月50回・5年分データ) の2プラン。年額¥9,800で45%OFF、7日間無料トライアル付き。",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "料金プラン — 月額¥1,480で月50回のAI分析",
    description:
      "Free (1日5回) と Pro (月¥1,480・7日間無料トライアル) の2プラン。年額¥9,800で45%OFF。",
    url: "/pricing",
    type: "website",
  },
};

export default function PricingPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "ホーム", url: "/" },
          { name: "料金プラン", url: "/pricing" },
        ])}
      />
      <PricingClient />
    </>
  );
}
