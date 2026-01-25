export const theme = {
  fonts: {
    primary: 'Inter, system-ui, -apple-system, sans-serif',
    weight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800
    }
  },
  colors: {
    primary: '#FFFFFF',
    accent: '#00D084',
    background: '#0B0F1A',
    disclaimer: '#999999',
    shadow: 'rgba(0, 0, 0, 0.3)'
  },
  spacing: {
    small: 20,
    medium: 40,
    large: 60,
    xlarge: 80
  },
  layout: {
    contentWidth: 940,  // Leave 70px padding on each side
    safeZoneTop: 100,
    safeZoneBottom: 100
  }
};

export type Theme = typeof theme;
