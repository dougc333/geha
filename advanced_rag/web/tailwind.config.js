/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07110f",
        panel: "#0d1916",
        mint: "#64efb6",
        citron: "#d8fb77",
        fog: "#a7b6b0",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(100,239,182,.18), 0 24px 80px rgba(0,0,0,.3)",
      },
    },
  },
  plugins: [],
};
