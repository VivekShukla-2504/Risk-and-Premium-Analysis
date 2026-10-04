/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17212E',
        paper: '#EEF1F4',
        panel: '#FFFFFF',
        rule: '#D3DAE2',
        muted: '#5B6877',
        sidebar: '#121C29',
        brand: { DEFAULT: '#16607A', dark: '#104A5F', tint: '#E4EEF2' },
        ochre: { DEFAULT: '#B98320', tint: '#F6EEDC' },
        brick: { DEFAULT: '#A24A42', tint: '#F4E4E2' },
        sage: { DEFAULT: '#4F7F5E', tint: '#E3EEE6' },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', '-apple-system', '"Segoe UI"', 'Roboto', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'Cambria', '"Times New Roman"', 'serif'],
      },
      borderRadius: { panel: '3px' },
    },
  },
  plugins: [],
};
