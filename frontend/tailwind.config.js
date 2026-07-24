/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef2ff", 100: "#e0e7ff", 200: "#c7d2fe", 500: "#6366f1", 600: "#4f46e5", 700: "#4338ca" },
      },
      boxShadow: {
        soft: "0 12px 35px -12px rgba(15,23,42,.16)",
        glow: "0 12px 35px -12px rgba(79,70,229,.45)",
      },
      animation: { "fade-in": "fadeIn .25s ease-out", "slide-up": "slideUp .25s ease-out" },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
