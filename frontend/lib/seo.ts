export const BASE_URL = "https://uma-build.vercel.app";

export const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "UmaBuild",
  url: BASE_URL,
  logo: `${BASE_URL}/icon.png`,
  description:
    "ノーコードで競馬予想AIを構築できるWebサービス。81の特徴量から選ぶだけで、LightGBMモデルを自動学習しバックテストで回収率を即確認。",
};

export const softwareAppJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "UmaBuild",
  applicationCategory: "UtilitiesApplication",
  operatingSystem: "Web",
  offers: [
    { "@type": "Offer", price: "0", priceCurrency: "JPY" },
    { "@type": "Offer", price: "1480", priceCurrency: "JPY" },
  ],
  description:
    "競馬の予想AIをプログラミングなしで作れるWebサービス。81の特徴量から選ぶだけで、LightGBMモデルを自動学習し、バックテストで回収率を即確認。",
  url: BASE_URL,
};

type BreadcrumbItem = { name: string; url: string };

export function breadcrumbJsonLd(items: BreadcrumbItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: item.url.startsWith("http") ? item.url : `${BASE_URL}${item.url}`,
    })),
  };
}

type FaqItem = { q: string; a: string };

export function faqPageJsonLd(faqs: FaqItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.a,
      },
    })),
  };
}
