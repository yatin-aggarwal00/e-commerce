import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm, furniture-store neutral palette.
        brand: {
          50: "#faf7f2",
          100: "#f1e9dd",
          200: "#e2d2bc",
          300: "#cdb18c",
          400: "#b8905f",
          500: "#a4763f",
          600: "#8a5f32",
          700: "#6f4a2b",
          800: "#5b3e28",
          900: "#4b3423",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
