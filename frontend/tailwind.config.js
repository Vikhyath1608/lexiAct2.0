/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary:  '#7C3AED',
        'primary-light': '#A78BFA',
        'primary-pale':  '#EDE9FE',
        accent:   '#2563EB',
        'accent-light':  '#60A5FA',
      },
      animation: {
        'fade-up':   'fadeUp 0.2s ease',
        'pulse-dot': 'pulseDot 1.2s ease-in-out infinite',
      },
      keyframes: {
        fadeUp:   { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
        pulseDot: { '0%,80%,100%': { transform: 'scale(0.8)', opacity: '0.5' }, '40%': { transform: 'scale(1.2)', opacity: '1' } },
      },
    },
  },
  plugins: [],
}
