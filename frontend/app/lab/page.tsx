import type { Metadata } from "next";
import { LabClient } from "./LabClient";
import { JsonLd } from "@/components/seo/JsonLd";
import { breadcrumbJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: "競馬AI構築ラボ — 特徴量を選んでLightGBMモデルを学習",
  description:
    "81の特徴量から選ぶだけで、競馬予想AIをノーコードで構築。LightGBMが自動学習し、バックテストで回収率を即確認できるAI Lab。",
  alternates: { canonical: "/lab" },
  openGraph: {
    title: "競馬AI構築ラボ — 特徴量を選んでLightGBMモデルを学習",
    description:
      "81の特徴量から選ぶだけで、競馬予想AIをノーコードで構築。LightGBMが自動学習し、バックテストで回収率を即確認できるAI Lab。",
    url: "/lab",
    type: "website",
  },
};

export default function LabPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "ホーム", url: "/" },
          { name: "AI Lab", url: "/lab" },
        ])}
      />
      <LabClient />
    </>
  );
}
