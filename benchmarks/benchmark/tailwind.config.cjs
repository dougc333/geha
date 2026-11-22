module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {
    colors: {
      ink: '#091020', panel: '#101b30', line: '#263753', muted: '#9aaac1',
      aqua: '#52dcf4', mint: '#68e5b5', gold: '#ffe164'
    },
    fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] }
  } },
  plugins: []
};
