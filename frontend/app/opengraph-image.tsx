import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "UmaBuild — ノーコード競馬予想AIビルダー";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background:
            "linear-gradient(135deg, #0A0A0F 0%, #13131A 50%, #0A0A0F 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "60px",
          position: "relative",
        }}
      >
        {/* Yellow radial glow */}
        <div
          style={{
            position: "absolute",
            top: "0",
            left: "50%",
            transform: "translateX(-50%)",
            width: "800px",
            height: "400px",
            background:
              "radial-gradient(ellipse, rgba(245, 233, 50, 0.12), transparent 70%)",
          }}
        />
        <div
          style={{
            fontSize: "80px",
            fontWeight: 700,
            color: "#F5E932",
            marginBottom: "24px",
            textShadow: "0 0 60px rgba(245, 233, 50, 0.5)",
            display: "flex",
          }}
        >
          UmaBuild
        </div>
        <div
          style={{
            fontSize: "36px",
            fontWeight: 500,
            color: "#F5F5F7",
            marginBottom: "16px",
            textAlign: "center",
            display: "flex",
          }}
        >
          ノーコード競馬予想AIビルダー
        </div>
        <div
          style={{
            fontSize: "22px",
            color: "#B4B4BE",
            textAlign: "center",
            maxWidth: "800px",
            display: "flex",
          }}
        >
          特徴量を選ぶだけで、あなただけの競馬AIが3分で完成
        </div>
        {/* Accent bar */}
        <div
          style={{
            marginTop: "40px",
            width: "120px",
            height: "4px",
            background:
              "linear-gradient(90deg, transparent, #F5E932, transparent)",
            borderRadius: "2px",
            display: "flex",
          }}
        />
      </div>
    ),
    { ...size }
  );
}
