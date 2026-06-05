/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f172a',    // slate-900
        surface: '#1e293b',       // slate-800
        primary: '#8b5cf6',       // violet-500
        secondary: '#3b82f6',     // blue-500
        accent: '#f43f5e',        // rose-500
        textMain: '#f8fafc',      // slate-50
        textMuted: '#94a3b8',     // slate-400
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 3s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        }
      }
    },
  },
  plugins: [],
}
