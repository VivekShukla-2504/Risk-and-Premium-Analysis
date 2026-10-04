/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1D2B26',
        paper: '#F3F2EC',
        panel: '#FFFEFA',
        rule: '#D9DCD4',
        muted: '#66736C',
        sidebar: '#18372F',
        brand: { DEFAULT: '#24745D', dark: '#195C49', tint: '#E7F0EB' },
        ochre: { DEFAULT: '#B8793D', tint: '#F6EDE1' },
        brick: { DEFAULT: '#A45449', tint: '#F5E9E5' },
        sage: { DEFAULT: '#5B8667', tint: '#E8F0E8' },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'Cambria', '"Times New Roman"', 'serif'],
      },
      borderRadius: { panel: '6px' },
    },
  },
  plugins: [],
};
