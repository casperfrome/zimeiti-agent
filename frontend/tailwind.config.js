/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        sage: {
          50: '#F4F8F1',
          100: '#E5EFDE',
          200: '#CCDEC0',
          300: '#A8C597',
          400: '#8FB87A',
          500: '#7AAB63',
          600: '#5F8E4B',
          700: '#4A6E3B',
        },
        ink: {
          DEFAULT: '#1F2A1E',
          soft: '#5A6358',
          mute: '#8E9489',
        },
        surface: '#FFFFFF',
        canvas: '#FAFBF7',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro SC"',
          '"SF Pro Display"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          'system-ui',
          'sans-serif',
        ],
      },
      borderRadius: {
        ios: '14px',
        sheet: '20px',
      },
      boxShadow: {
        card: '0 2px 12px rgba(31,42,30,0.06)',
        float: '0 8px 32px rgba(31,42,30,0.10)',
        inset: 'inset 0 0 0 1px rgba(31,42,30,0.06)',
      },
      backdropBlur: {
        ios: '20px',
      },
    },
  },
  plugins: [],
}
