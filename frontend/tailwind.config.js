/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f2f5ff",
          100: "#e6ebff",
          200: "#cdd7fe",
          500: "#5368d9",
          600: "#4054c7",
          700: "#3443a2",
        },
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15,23,42,.04), 0 4px 16px rgba(15,23,42,.04)",
      },
    },
  },
  plugins: [],
};
