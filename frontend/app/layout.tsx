import type { Metadata } from "next";
import { Noto_Sans_JP, Shippori_Mincho, DM_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";

const notoSansJP = Noto_Sans_JP({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-sans",
});

const shipporiMincho = Shippori_Mincho({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-mincho",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  variable: "--font-mono",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://uma-build.vercel.app"),
  title: {
    default: "UmaBuild — ノーコード競馬予想AIビルダー",
    template: "%s | UmaBuild",
  },
  description:
    "競馬の予想AIをプログラミングなしで作れる。81の特徴量から選ぶだけで、LightGBMが自動学習。バックテストで回収率を即確認。",
  keywords: [
    "競馬AI",
    "競馬予想",
    "ノーコード",
    "LightGBM",
    "バックテスト",
    "回収率",
    "機械学習",
    "UmaBuild",
  ],
  openGraph: {
    title: "UmaBuild — ノーコード競馬予想AIビルダー",
    description:
      "競馬の予想AIをプログラミングなしで作れる。81の特徴量から選ぶだけで、LightGBMが自動学習。",
    type: "website",
    locale: "ja_JP",
    siteName: "UmaBuild",
  },
  twitter: {
    card: "summary_large_image",
    title: "UmaBuild — ノーコード競馬予想AIビルダー",
    description:
      "競馬の予想AIをプログラミングなしで作れる。81の特徴量から選ぶだけで、LightGBMが自動学習。",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className={`dark ${notoSansJP.variable} ${shipporiMincho.variable} ${dmMono.variable}`}>
      <body className="font-sans antialiased text-text-primary min-h-screen flex flex-col">
        <Providers>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
