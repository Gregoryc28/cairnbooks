import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        newsprint: "#FAF7F0",
        ink: "#121316",
        coral: "#FF4C38",
        lime: "#CEFF00",
        halftone: "#E6E2D8",
      },
      fontFamily: {
        serif: ["var(--font-fraunces)", "Georgia", "serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      boxShadow: {
        riso: "4px 4px 0px #121316",
        "riso-sm": "2px 2px 0px #121316",
        "riso-lg": "6px 6px 0px #121316",
      },
    },
  },
  plugins: [],
};

export default config;
