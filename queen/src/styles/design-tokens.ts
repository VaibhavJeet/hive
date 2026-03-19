/**
 * Design Tokens - worldmonitor inspired design system
 * Clean, professional, monospace-focused dashboard aesthetic
 */

export const colors = {
  // Backgrounds
  bg: '#0a0a0a',
  bgSecondary: '#111111',
  surface: '#141414',
  surfaceHover: '#1e1e1e',
  surfaceActive: '#1a1a2e',

  // Borders
  border: '#2a2a2a',
  borderStrong: '#444444',
  borderSubtle: '#1a1a1a',

  // Text
  text: '#e8e8e8',
  textSecondary: '#a0a0a0',
  textDim: '#888888',
  textMuted: '#666666',
  textFaint: '#555555',
  textGhost: '#444444',
  accent: '#ffffff',

  // Overlays
  overlaySubtle: 'rgba(255, 255, 255, 0.03)',
  overlayLight: 'rgba(255, 255, 255, 0.05)',
  overlayMedium: 'rgba(255, 255, 255, 0.1)',
  overlayHeavy: 'rgba(255, 255, 255, 0.2)',

  // Shadows
  shadowColor: 'rgba(0, 0, 0, 0.5)',
  darkenLight: 'rgba(0, 0, 0, 0.15)',
  darkenMedium: 'rgba(0, 0, 0, 0.2)',
  darkenHeavy: 'rgba(0, 0, 0, 0.3)',

  // Semantic - Status
  semantic: {
    critical: '#ff4444',
    high: '#ff8800',
    elevated: '#ffaa00',
    normal: '#44aa44',
    low: '#3388ff',
    info: '#3b82f6',
    positive: '#44ff88',
  },

  // Status indicators
  status: {
    live: '#44ff88',
    cached: '#ffaa00',
    unavailable: '#ff4444',
    online: '#44ff88',
    offline: '#ff4444',
    pending: '#ffaa00',
  },

  // Input
  inputBg: '#1a1a1a',

  // Panel
  panelBg: '#141414',
  panelBorder: '#2a2a2a',

  // Scrollbar
  scrollbarThumb: '#333333',
  scrollbarThumbHover: '#555555',
} as const;

export const typography = {
  fontMono: "'SF Mono', 'Monaco', 'Cascadia Code', 'Fira Code', 'DejaVu Sans Mono', 'Liberation Mono', 'Consolas', monospace",
  fontSystem: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",

  // Font sizes
  sizes: {
    xs: '10px',      // Labels, badges
    sm: '11px',      // Tabs, small text
    base: '12px',    // Body text
    md: '13px',      // Slightly larger body
    lg: '14px',      // Headers
    xl: '16px',      // Large headers
    '2xl': '18px',   // Section titles
    '3xl': '24px',   // Page titles
  },

  // Line heights
  lineHeight: {
    tight: 1.2,
    normal: 1.5,
    relaxed: 1.7,
  },

  // Font weights
  weight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },

  // Letter spacing
  tracking: {
    tight: '-0.01em',
    normal: '0',
    wide: '0.03em',
    wider: '0.05em',
  },
} as const;

export const spacing = {
  px: '1px',
  0: '0',
  0.5: '2px',
  1: '4px',
  1.5: '6px',
  2: '8px',
  2.5: '10px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
} as const;

export const borderRadius = {
  none: '0',
  sm: '2px',
  base: '4px',
  md: '6px',
  lg: '8px',
  xl: '12px',
  full: '9999px',
} as const;

export const shadows = {
  sm: '0 1px 2px rgba(0, 0, 0, 0.3)',
  base: '0 2px 4px rgba(0, 0, 0, 0.3)',
  md: '0 4px 8px rgba(0, 0, 0, 0.4)',
  lg: '0 8px 16px rgba(0, 0, 0, 0.5)',
  xl: '0 12px 24px rgba(0, 0, 0, 0.6)',
  inner: 'inset 0 1px 2px rgba(0, 0, 0, 0.3)',
  glow: {
    green: '0 0 8px rgba(68, 255, 136, 0.3)',
    red: '0 0 8px rgba(255, 68, 68, 0.3)',
    blue: '0 0 8px rgba(59, 130, 246, 0.3)',
    yellow: '0 0 8px rgba(255, 170, 0, 0.3)',
  },
} as const;

export const transitions = {
  fast: '0.1s ease',
  base: '0.15s ease',
  normal: '0.2s ease',
  slow: '0.3s ease',
} as const;

export const zIndex = {
  dropdown: 100,
  sticky: 200,
  modal: 300,
  overlay: 400,
  toast: 500,
} as const;
