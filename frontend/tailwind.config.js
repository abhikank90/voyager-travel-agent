/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        voyager: {
          blue: '#0066CC',
          teal: '#00A896',
          sand: '#F5E6CC',
          ocean: '#003D6B',
          sunset: '#FF6B35',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
