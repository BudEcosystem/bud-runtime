// export const apiBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;
// export const tempApiBaseUrl = process.env.NEXT_PUBLIC_TEMP_API_BASE_URL;
export const apiBaseUrl =
  process.env.NEXT_PUBLIC_BASE_URL?.replace(/\/+$/, "") || "";
export const tempApiBaseUrl =
  process.env.NEXT_PUBLIC_TEMP_API_BASE_URL?.replace(/\/+$/, "") || "";
export const assetBaseUrl = `${tempApiBaseUrl}/static/`;
export const webSocketUrl = process.env.NEXT_PUBLIC_NOVU_SOCKET_URL;
export const novuBackendUrl = process.env.NEXT_PUBLIC_NOVU_BASE_URL;
export const novuSocketUrl = process.env.NEXT_PUBLIC_NOVU_SOCKET_URL;
export const novuAppId = process.env.NEXT_PUBLIC_NOVU_APP_ID;
export const playGroundUrl = process.env.NEXT_PUBLIC_PLAYGROUND_URL;
export const askBudUrl = process.env.NEXT_PUBLIC_ASK_BUD_URL;
export const askBudModel = process.env.NEXT_PUBLIC_ASK_BUD_MODEL;
export const enableDevMode = process.env.NEXT_PUBLIC_ENABLE_DEV_MODE === 'true';
export const observabilitySocketUrl = process.env.NEXT_PUBLIC_OBSERVABILITY_SOCKET_URL;

// Branding configuration with defaults
export const branding = {
  // Main logo for dashboard sidebar and header
  logoUrl: process.env.NEXT_PUBLIC_LOGO_URL || '/images/logo.svg',
  // Logo for auth pages (login/register)
  logoAuthUrl: process.env.NEXT_PUBLIC_LOGO_AUTH_URL || '/images/BudLogo.png',
  // Favicon for browser tab
  faviconUrl: process.env.NEXT_PUBLIC_FAVICON_URL || '/favicon.ico',
};
