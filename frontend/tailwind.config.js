/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Sora', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        // Erphoria ERP navy palette
        bg:       '#060d1a',
        sidebar:  '#080f1e',
        surface:  '#0d1829',
        surface2: '#112035',
        surface3: '#162540',
        line:     'rgba(255,255,255,0.07)',
        line2:    'rgba(255,255,255,0.12)',
        ink:    { DEFAULT: '#e8edf8', soft: '#8b9ab8', faint: '#4d607a' },
        brand:  { DEFAULT: '#3b82f6', 2: '#60a5fa', 3: '#1d4ed8', glow: 'rgba(59,130,246,0.25)' },
        cyan:   { DEFAULT: '#06b6d4', soft: 'rgba(6,182,212,0.15)' },
        violet: { DEFAULT: '#8b5cf6', soft: 'rgba(139,92,246,0.15)' },
        good:   { DEFAULT: '#10b981', soft: 'rgba(16,185,129,0.15)' },
        warn:   { DEFAULT: '#f59e0b', soft: 'rgba(245,158,11,0.15)' },
        crit:   { DEFAULT: '#ef4444', soft: 'rgba(239,68,68,0.15)' },
      },
      boxShadow: {
        card:  '0 1px 0 rgba(255,255,255,0.05) inset, 0 20px 50px rgba(0,0,0,0.5)',
        glow:  '0 0 0 1px rgba(59,130,246,0.3), 0 8px 32px rgba(59,130,246,0.15)',
      },
      backgroundImage: {
        'brand-grad': 'linear-gradient(135deg, #2563eb 0%, #3b82f6 50%, #60a5fa 100%)',
      },
      keyframes: {
        'fade-up':  { '0%': { opacity: 0, transform: 'translateY(12px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        float:      { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-12px)' } },
        shimmer:    { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        spinslow:   { to: { transform: 'rotate(360deg)' } },
        pulseglow:  { '0%,100%': { opacity: 0.5 }, '50%': { opacity: 1 } },
        'slide-in': { '0%': { opacity: 0, transform: 'translateX(-16px)' }, '100%': { opacity: 1, transform: 'translateX(0)' } },
      },
      animation: {
        'fade-up':  'fade-up .5s cubic-bezier(.2,.7,.2,1) both',
        float:      'float 6s ease-in-out infinite',
        shimmer:    'shimmer 2.5s linear infinite',
        spinslow:   'spinslow 1s linear infinite',
        pulseglow:  'pulseglow 2s ease-in-out infinite',
        'slide-in': 'slide-in .4s cubic-bezier(.2,.7,.2,1) both',
      },
    },
  },
  plugins: [],
};
