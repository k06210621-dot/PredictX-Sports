/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#0ea5e9', // sky-500
        'secondary': '#0284c7', // sky-600
        'accent': '#f59e0b', // amber-500
        'dark-bg': '#0f172a', // slate-900
        'dark-card': '#1e293b', // slate-800
        'light-text': '#f8fafc', // slate-50
        'muted-text': '#94a3b8', // slate-400
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan-line': 'scan-line 8s linear infinite',
      },
      keyframes: {
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
