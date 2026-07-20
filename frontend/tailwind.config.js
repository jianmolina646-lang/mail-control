/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0b0d12',
        panel: '#12151d',
        edge: '#1f2430',
        accent: '#e50914',
        gold: '#d4af37',
      },
    },
  },
  plugins: [],
}
