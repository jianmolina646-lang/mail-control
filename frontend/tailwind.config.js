/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f7f2ff",
          100: "#eee3ff",
          200: "#ddc8ff",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
        },
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15,23,42,.04), 0 4px 16px rgba(15,23,42,.04)",
      },
    },
  },
  plugins: [],
};
