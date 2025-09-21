// DEPRECATED: Use useApiConfig() hook from EnvironmentProvider instead
// This file is kept for backward compatibility but should be migrated

import { getClientEnvironment } from "@/lib/environment";

const clientEnv = getClientEnvironment();

export const assetBaseUrl = clientEnv.assetBaseUrl || "";
export const tempApiBaseUrl = clientEnv.baseUrl || "http://localhost:3000";
export const apiBaseUrl =
  process.env.NEXT_PUBLIC_BASE_URL?.replace(/\/+$/, "") || "";
export const webSocketUrl = process.env.NEXT_PUBLIC_NOVU_SOCKET_URL;
export const novuBackendUrl = process.env.NEXT_PUBLIC_NOVU_BASE_URL;
export const novuSocketUrl = process.env.NEXT_PUBLIC_NOVU_SOCKET_URL;
export const novuAppId = process.env.NEXT_PUBLIC_NOVU_APP_ID;
export const playGroundUrl = process.env.NEXT_PUBLIC_PLAYGROUND_URL;
export const askBudUrl = process.env.NEXT_PUBLIC_ASK_BUD_URL;
export const askBudModel = process.env.NEXT_PUBLIC_ASK_BUD_MODEL;
