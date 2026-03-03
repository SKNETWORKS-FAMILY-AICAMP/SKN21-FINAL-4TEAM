import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#e91e63',
          light: 'rgba(233,30,99,0.15)',
          dark: '#c2185b',
        },
        secondary: '#9c27b0',
        dark: {
          DEFAULT: '#121212',
          surface: '#1e1e2e',
        },
        success: '#4caf50',
        warning: '#ff9800',
        danger: {
          DEFAULT: '#f44336',
          text: '#ef5350',
          cost: '#ff7043',
        },
        text: {
          DEFAULT: '#e0e0e0',
          secondary: '#9e9e9e',
          muted: '#616161',
          label: '#bdbdbd',
        },
        bg: {
          DEFAULT: '#1a1a1a',
          surface: '#262626',
          hover: '#333333',
          tag: '#333333',
          input: '#1e1e1e',
          muted: '#3a3a3a',
        },
        border: {
          DEFAULT: '#333333',
          input: '#444444',
          delete: '#5c2020',
        },
      },
      fontFamily: {
        sans: ['Pretendard', 'sans-serif'],
      },
      borderRadius: {
        badge: '10px',
      },
      boxShadow: {
        card: '0 4px 20px rgba(0,0,0,0.4)',
        bubble: '0 1px 4px rgba(0,0,0,0.3)',
        glow: '0 0 15px rgba(233,30,99,0.3)',
      },
      keyframes: {
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(100%)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-in-left': {
          '0%': { opacity: '0', transform: 'translateX(-100%)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateX(-50%) translateY(0)' },
          '15%': { opacity: '1', transform: 'translateX(-50%) translateY(8px)' },
          '70%': { opacity: '1', transform: 'translateX(-50%) translateY(8px)' },
          '100%': { opacity: '0', transform: 'translateX(-50%) translateY(24px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
      },
      animation: {
        'slide-in': 'slide-in 0.25s ease-out',
        'slide-in-left': 'slide-in-left 0.25s ease-out',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 3s ease-out forwards',
        shimmer: 'shimmer 2s linear infinite',
      },
    },
  },
  plugins: [],
};

export default config;
