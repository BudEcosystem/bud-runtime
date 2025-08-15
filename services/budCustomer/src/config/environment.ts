// Environment configuration
// DEPRECATED: Use usePlaygroundConfig() hook from EnvironmentProvider instead
// This file is kept for backward compatibility but should be migrated

import { getClientEnvironment } from "@/lib/environment";

const clientEnv = getClientEnvironment();

export const playGroundUrl = clientEnv.playgroundUrl || "http://localhost:3001";
export const askBudUrl = clientEnv.askBudUrl || "";
export const askBudModel = clientEnv.askBudModel || "gpt-4";
