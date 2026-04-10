import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'sovereign-black': '#050505',
        'sovereign-secondary': '#0A0A0C',
        'sovereign-indigo': '#3C3489',
        'sovereign-teal': '#1D9E75',
      },
      fontFamily: {
        sans: ['var(--font-inter)'],
      },
      letterSpacing: {
        'tighter': '-0.04em',
      },
    },
  },
  plugins: [],
}
export default config