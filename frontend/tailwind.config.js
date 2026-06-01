/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Sora', 'Inter', 'sans-serif'],
      },
      colors: {
        bg: '#07070d',
        surface: '#10111c',
        surface2: '#161827',
        line: 'rgba(255,255,255,0.08)',
        ink: { DEFAULT: '#eceefb', soft: '#9aa0bd', faint: '#6b7090' },
        brand: { DEFAULT: '#7c5cff', 2: '#a855f7', 3: '#ec4899' },
        cyan: '#22d3ee',
        good: '#34d399', warn: '#fbbf24', crit: '#fb7185',
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(124,92,255,.25), 0 10px 40px -10px rgba(124,92,255,.45)',
        card: '0 1px 0 rgba(255,255,255,.04) inset, 0 20px 50px -20px rgba(0,0,0,.7)',
      },
      backgroundImage: {
        'brand-grad': 'linear-gradient(135deg, #7c5cff 0%, #a855f7 50%, #ec4899 100%)',
        'glow-radial': 'radial-gradient(60% 60% at 50% 0%, rgba(124,92,255,.18) 0%, rgba(7,7,13,0) 70%)',
      },
      keyframes: {
        'fade-up': { '0%': { opacity: 0, transform: 'translateY(14px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        float: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-14px)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        spinslow: { to: { transform: 'rotate(360deg)' } },
        pulseglow: { '0%,100%': { opacity: .6 }, '50%': { opacity: 1 } },
      },
      animation: {
        'fade-up': 'fade-up .6s cubic-bezier(.2,.7,.2,1) both',
        float: 'float 6s ease-in-out infinite',
        shimmer: 'shimmer 2.5s linear infinite',
        spinslow: 'spinslow 1.1s linear infinite',
        pulseglow: 'pulseglow 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
