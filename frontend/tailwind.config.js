/** @type {import('tailwindcss').Config} */
export default {
  content: ['./app.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        main: '#0b1120',
        card: '#111827',
        terminal: '#050810',
        brand: '#2563eb',
        'brand-hover': '#3b82f6',
        'brand-text': '#60a5fa',
        'brand-border': '#1e40af',
        success: '#34d399',
        error: '#ef4444',
        primary: '#ffffff',
        secondary: '#e2e8f0',
        muted: '#94a3b8',
        dim: '#64748b',
        placeholder: '#475569',
        'border-default': '#1e293b',
        'border-light': '#334155',
      },
    },
  },
  plugins: [],
};
