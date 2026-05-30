/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'SF Pro Text',
               'Inter', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'sans-serif'],
      },
      colors: {
        ink: { DEFAULT: '#1d1d1f', soft: '#6e6e73', faint: '#86868b' },
        canvas: '#f5f5f7',
        accent: { DEFAULT: '#0071e3', hover: '#0077ed' },
        good: '#34c759', warn: '#ff9f0a', crit: '#ff3b30',
      },
      borderRadius: { '2xl': '1.25rem', '3xl': '1.75rem' },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04)',
        hover: '0 2px 6px rgba(0,0,0,0.06), 0 16px 40px rgba(0,0,0,0.08)',
      },
      keyframes: {
        'fade-up': { '0%': { opacity: 0, transform: 'translateY(8px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        'pop': { '0%': { transform: 'scale(0.96)' }, '100%': { transform: 'scale(1)' } },
      },
      animation: { 'fade-up': 'fade-up .5s cubic-bezier(.2,.7,.2,1) both', 'pop': 'pop .3s ease both' },
    },
  },
  plugins: [],
};
