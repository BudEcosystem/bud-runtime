export const apiBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;
export const tempApiBaseUrl = process.env.NEXT_PUBLIC_TEMP_API_BASE_URL;
export const assetBaseUrl = `${tempApiBaseUrl}/static/`;
export const webSocketUrl = process.env.NEXT_PUBLIC_NOVU_SOCKET_URL;
export const novuBackendUrl = process.env.NEXT_PUBLIC_NOVU_BASE_URL;
export const novuSocketUrl = process.env.NEXT_PUBLIC_NOVU_SOCKET_URL;
export const novuAppId = process.env.NEXT_PUBLIC_NOVU_APP_ID;
export const copyCodeApiBaseUrl = process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL;
export const OpenAiKey = process.env.NEXT_PUBLIC_OPENAI_API_KEY;

export const apiKey = 'budserve_NgMnHOzyQjCXGgmoFZrYNwS7LgqZU2VMcmz3bz4U';


console.log('apiBaseUrl', apiBaseUrl);
console.log('tempApiBaseUrl', tempApiBaseUrl);
console.log('assetBaseUrl', assetBaseUrl);
console.log('copyCodeApiBaseUrl', copyCodeApiBaseUrl);