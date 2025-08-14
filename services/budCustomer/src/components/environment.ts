// DEPRECATED: Use useApiConfig() hook from EnvironmentProvider instead
// This file is kept for backward compatibility but should be migrated

import { getClientEnvironment } from "@/lib/environment";

const clientEnv = getClientEnvironment();

export const assetBaseUrl = clientEnv.assetBaseUrl || "";
export const tempApiBaseUrl = clientEnv.baseUrl || "http://localhost:3000";
