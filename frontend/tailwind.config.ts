import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        kiosk: {
          teal: {
            50: "#f0fdfa",
            100: "#ccfbf1",
            500: "#14b8a6",
            600: "#0d9488",
            700: "#0f766e",
            800: "#115e59",
            900: "#134e4a",
          },
          slate: {
            800: "#1e293b",
            900: "#0f172a",
          },
          accent: "#2563eb",
          urgent: "#dc2626",
          success: "#16a34a",
        },
      },
      fontSize: {
        'kiosk-xl': ['2.25rem', { lineHeight: '2.75rem' }],
        'kiosk-2xl': ['3rem', { lineHeight: '3.5rem' }],
      },
    },
  },
  plugins: [],
};

export default config;
