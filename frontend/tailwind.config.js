/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#004625',
          container: '#1e5e3a',
          fixed: '#aff2c2',
        },
        secondary: {
          DEFAULT: '#904d00',
          container: '#d97706',
          fixed: '#ffdcc3',
        },
        surface: {
          DEFAULT: '#f9f9ff',
          container: '#eef3ee',
          low: '#f4f7f4',
          high: '#e4ebe3',
        },
        mandi: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          900: '#14532d',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
