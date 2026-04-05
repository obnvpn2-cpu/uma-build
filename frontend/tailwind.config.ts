import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#F5E932",
          dark: "#E0D020",
          light: "#FFF373",
          glow: "rgba(245, 233, 50, 0.45)",
        },
        surface: {
          DEFAULT: "#0A0A0F",
          raised: "#13131A",
          overlay: "#1A1A24",
          border: "#2A2A35",
        },
        text: {
          primary: "#F5F5F7",
          secondary: "#B4B4BE",
          muted: "#6E6E78",
        },
        success: "#4ADE80",
        warning: "#FBBF24",
        danger: "#F87171",
      },
      fontFamily: {
        mincho: ["var(--font-mincho)", "Shippori Mincho", "serif"],
        mono: ["var(--font-mono)", "DM Mono", "monospace"],
        sans: ["var(--font-sans)", "Noto Sans JP", "sans-serif"],
      },
      boxShadow: {
        "glow-yellow": "0 0 24px rgba(245, 233, 50, 0.35)",
        "glow-yellow-lg": "0 0 40px rgba(245, 233, 50, 0.55)",
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};
export default config;
