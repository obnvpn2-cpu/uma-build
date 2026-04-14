import type { Metadata } from "next";
import Script from "next/script";
import { Noto_Sans_JP, Shippori_Mincho, DM_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";

const GTM_ID = process.env.NEXT_PUBLIC_GTM_ID;

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
      <head>
        {GTM_ID && (
          <Script
            id="gtm"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
              __html: `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','${GTM_ID}');`,
            }}
          />
        )}
      </head>
      <body className="font-sans antialiased text-text-primary min-h-screen flex flex-col">
        {GTM_ID && (
          <noscript>
            <iframe
              src={`https://www.googletagmanager.com/ns.html?id=${GTM_ID}`}
              height="0"
              width="0"
              style={{ display: "none", visibility: "hidden" }}
            />
          </noscript>
        )}
        <Providers>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
