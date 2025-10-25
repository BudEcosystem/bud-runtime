import '@testing-library/jest-dom/vitest';

if (!window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
    media: '',
    onchange: null,
  }) as MediaQueryList;
}
