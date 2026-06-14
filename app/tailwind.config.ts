import type { Config } from "tailwindcss";


const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "Noto Sans JP", "system-ui", "sans-serif"],
        jp: ["Klee One", "Noto Sans JP", "serif"],
        display: ["Yusei Magic", "Klee One", "Noto Sans JP", "serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        washi: {
          50: "#fbf8f1",
          100: "#f6efe0",
          200: "#ede2c6",
          300: "#dccda4",
          400: "#b9a37e",
          500: "#8c785a",
          900: "#1f1a14",
          950: "#141009",
        },
        shu: {
          // 朱 — vermilion accent
          400: "#e26b5a",
          500: "#d8442f",
          600: "#b9351f",
          700: "#8f2917",
        },
        sakura: {
          200: "#ffd9d9",
          300: "#ffb8c0",
          400: "#ff8aa1",
        },
        ink: {
          DEFAULT: "#171311",
          soft: "#2a2420",
        },
      },
      boxShadow: {
        panel: "0 1px 0 rgba(255,255,255,0.04), 0 8px 24px rgba(0,0,0,0.35)",
        glow: "0 0 0 1px rgba(216,68,47,0.4), 0 0 24px rgba(216,68,47,0.25)",
      },
      backgroundImage: {
        "washi-grain":
          "radial-gradient(rgba(140,120,90,0.08) 1px, transparent 1px), radial-gradient(rgba(140,120,90,0.05) 1px, transparent 1px)",
      },
      backgroundSize: {
        "washi-grain": "16px 16px, 32px 32px",
      },
    },
  },
  plugins: [],
};

export default config;
