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
          DEFAULT: "#58A6FF",
          dark: "#388BFD",
          light: "#79C0FF",
        },
        surface: {
          DEFAULT: "#0D1117",
          raised: "#161B22",
          overlay: "#1C2128",
          border: "#30363D",
        },
        text: {
          primary: "#F0F6FC",
          secondary: "#9DA5AE",
          muted: "#7D8590",
        },
        success: "#3FB950",
        warning: "#D29922",
        danger: "#F85149",
      },
      fontFamily: {
        mincho: ["var(--font-mincho)", "Shippori Mincho", "serif"],
        mono: ["var(--font-mono)", "DM Mono", "monospace"],
        sans: ["var(--font-sans)", "Noto Sans JP", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
