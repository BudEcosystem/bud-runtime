// Environment configuration utility that picks up variables from both .env files and runtime
// This approach works with Next.js App Router and provides server-side environment injection

export interface EnvironmentConfig {
  playgroundUrl: string;
  askBudUrl: string;
  askBudModel: string;
  assetBaseUrl: string;
  baseUrl: string;
  novuBaseUrl: string;
  novuSocketUrl: string;
  copyCodeApiBaseUrl: string;
  privateKey: string;
  password: string;
}

// Server-side function to get environment variables
// This will pick up both .env file variables and runtime environment variables
export function getServerEnvironment(): EnvironmentConfig {
  return {
    playgroundUrl:
      process.env.NEXT_PUBLIC_PLAYGROUND_URL || "http://localhost:3001",
    askBudUrl: process.env.NEXT_PUBLIC_ASK_BUD_URL || "",
    askBudModel: process.env.NEXT_PUBLIC_ASK_BUD_MODEL || "gpt-4",
    assetBaseUrl: process.env.NEXT_PUBLIC_ASSET_BASE_URL || "",
    baseUrl: process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000",
    novuBaseUrl: process.env.NEXT_PUBLIC_NOVU_BASE_URL || "",
    novuSocketUrl: process.env.NEXT_PUBLIC_NOVU_SOCKET_URL || "",
    copyCodeApiBaseUrl: process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL || "",
    privateKey: process.env.NEXT_PUBLIC_PRIVATE_KEY || "",
    password: process.env.NEXT_PUBLIC_PASSWORD || "",
  };
}

// Client-side fallback function (for client components that still need env vars)
// This should be used as a fallback when server-side injection is not available
export function getClientEnvironment(): Partial<EnvironmentConfig> {
  if (typeof window === "undefined") {
    // If running on server, return empty object to prevent hydration issues
    return {};
  }

  return {
    playgroundUrl:
      process.env.NEXT_PUBLIC_PLAYGROUND_URL || "http://localhost:3001",
    askBudUrl: process.env.NEXT_PUBLIC_ASK_BUD_URL || "",
    askBudModel: process.env.NEXT_PUBLIC_ASK_BUD_MODEL || "gpt-4",
    assetBaseUrl: process.env.NEXT_PUBLIC_ASSET_BASE_URL || "",
    baseUrl: process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000",
    novuBaseUrl: process.env.NEXT_PUBLIC_NOVU_BASE_URL || "",
    novuSocketUrl: process.env.NEXT_PUBLIC_NOVU_SOCKET_URL || "",
    copyCodeApiBaseUrl: process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL || "",
  };
}

// Type guard to check if environment config is complete
export function isCompleteEnvironment(
  env: Partial<EnvironmentConfig>,
): env is EnvironmentConfig {
  return !!env.baseUrl;
}
