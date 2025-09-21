import axios from "axios";
const baseUrl = process.env.NEXT_PUBLIC_BASE_URL;
import { errorToast } from "@/components/toast";

// OAuth Types
interface OAuthCallbackResponse {
  access_token: string;
  refresh_token?: string;
  user: {
    id: string;
    email: string;
    name: string;
    avatar?: string;
  };
}

interface TokenExchangeResponse {
  access_token: string;
  refresh_token?: string;
  user: {
    id: string;
    email: string;
    name: string;
    avatar?: string;
  };
}

export interface OAuthProvider {
  provider: string;
  enabled: boolean;
  display_name: string;
  icon_url?: string;
}

export interface OAuthProvidersResponse {
  success: boolean;
  message: string;
  result: {
    providers: OAuthProvider[];
    tenant_id: string;
  };
}

export const axiosInstance = axios.create({
  baseURL: baseUrl,
});

let Token: string | null = null;
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];
let isRedirecting = false;

if (typeof window !== "undefined") {
  Token = localStorage.getItem("access_token");
  // Reset isRedirecting flag if we're on the login page
  if (window.location.pathname === "/login") {
    isRedirecting = false;
  }
}

axiosInstance.interceptors.request.use(
  async (config) => {
    // ✅ Check Internet Connection
    if (typeof window !== "undefined" && !navigator.onLine) {
      errorToast("No internet connection");
      return Promise.reject(new Error("No internet connection"));
    }

    // ✅ Optional: Network quality check
    const connection =
      (navigator as any).connection ||
      (navigator as any)["mozConnection"] ||
      (navigator as any)["webkitConnection"];

    if (connection) {
      const { effectiveType, downlink } = connection;
      const slowConnection =
        ["2g", "slow-2g"].includes(effectiveType) || downlink < 0.5;

      if (slowConnection) {
        errorToast("Network is too slow or throttled");
        return Promise.reject(new Error("Poor network connection"));
      }
    }

    // 🛡️ Token check
    if (typeof window !== "undefined") {
      Token = localStorage.getItem("access_token");
    }

    const isPublicEndpoint =
      config.url?.includes("auth/login") ||
      config.url?.includes("auth/register") ||
      config.url?.includes("users/reset-password") ||
      config.url?.includes("users/validate-reset-token") ||
      config.url?.includes("users/reset-password-with-token") ||
      config.url?.includes("auth/refresh-token") ||
      config.url?.includes("auth/oauth/callback") ||
      config.url?.includes("auth/token/exchange") ||
      config.url?.includes("oauth/internal/authorize") ||
      config.url?.includes("oauth/providers");

    if (!Token && !isPublicEndpoint) {
      // Prevent redirect loop
      if (
        typeof window !== "undefined" &&
        window.location.pathname !== "/login"
      ) {
        if (!isRedirecting) {
          isRedirecting = true;
          localStorage.clear();
          window.location.replace("/login");
        }
      }
      return Promise.reject(new Error("No access token found"));
    }

    if (Token && config.headers) {
      config.headers.Authorization = `Bearer ${Token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onRefreshed(token: string) {
  refreshSubscribers.map((cb) => cb(token));
}

// Response interceptor
axiosInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  (err) => {
    const status = err?.response?.status;
    if (status === 401 && !isRefreshing) {
      isRefreshing = true;
      return refreshToken()
        .then((newToken) => {
          console.log("Token refresh successful");
          isRefreshing = false;
          onRefreshed(newToken);
          refreshSubscribers = [];
          return axiosInstance({
            ...err.config,
            headers: {
              ...err.config.headers,
              Authorization: `Bearer ${newToken}`,
            },
          });
        })
        .catch((err) => {
          console.log("Token refresh failed", err);
          isRefreshing = false;
          refreshSubscribers = [];
          // ✅ Don't rethrow if redirect already happened
          if (!isRedirecting) {
            return Promise.reject(err);
          }
          // If redirect already in progress, halt further processing
          return new Promise(() => {}); // Keeps the Promise pending
        });
    } else if (status === 401 && isRefreshing) {
      return new Promise((resolve) => {
        if (err.config?.url == "auth/refresh-token") {
          if (!isRedirecting) {
            isRedirecting = true;
            localStorage.clear();
            window.location.replace("/login");
          }
          return;
        }
        subscribeTokenRefresh((newToken: string) => {
          err.config.headers.Authorization = `Bearer ${newToken}`;
          resolve(axiosInstance(err.config));
        });
      });
    }
    return handleErrorResponse(err);
  },
);

const handleErrorResponse = (err: any) => {
  console.log("err.config?.url", err.config?.url);
  if (
    err.response &&
    err.response.status === 401 &&
    err.config?.url !== "auth/refresh-token"
  ) {
    if (!isRedirecting) {
      isRedirecting = true;
      localStorage.clear();
      window.location.replace("/login");
    }
    return false;
  }
  if (err.response && err.response.status === 401) {
    if (!isRedirecting) {
      isRedirecting = true;
      localStorage.clear();
      window.location.replace("/login");
      return false;
    }
  }
  if (err.response && err.response.status === 403) {
    console.log("403", err);
    if (err.config.url.includes("auth/refresh-token")) {
      localStorage.clear();
    } else {
      errorToast(err.response?.data?.message || err.response?.data?.detail);
    }
    return false;
  } else if (err.response && err.response.code === 500) {
    window.location.reload();
    return false;
  } else if (err.response && err.response.status === 500) {
    return Promise.reject(err);
  } else if (err.response && err.response.status === 422) {
    return Promise.reject(err);
  } else if (
    err.response &&
    err.response.status == 400 &&
    err.response.request.responseURL.includes("/login")
  ) {
    return Promise.reject(err.response.data);
  } else {
    console.log(err);
    // Only show error toast for endpoints that don't have explicit error handling in components
    // Avoid showing error toasts for endpoints where components handle their own errors
    const url = err.config?.url || "";
    const skipErrorToastEndpoints = [
      "/credentials/",
      "users/reset-password",
      "users/validate-reset-token",
      "users/reset-password-with-token",
      "/auth/login",
    ];

    const shouldShowErrorToast = !skipErrorToastEndpoints.some((endpoint) =>
      url.includes(endpoint),
    );

    if (shouldShowErrorToast && err && localStorage.getItem("access_token")) {
      console.log(err.response?.data?.message);
      errorToast(err.response?.data?.message);
    }
    return Promise.reject(err);
  }
};

const refreshToken = async () => {
  try {
    const refreshTokenValue = localStorage.getItem("refresh_token");

    if (!refreshTokenValue) {
      throw new Error("No refresh token found");
    }

    const payload = {
      refresh_token: refreshTokenValue,
    };

    const response = await axios.post(
      `${baseUrl}/auth/refresh-token`,
      payload,
      {
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    const data = response.data;

    if (!data?.token?.access_token) {
      throw new Error("No access token found in refresh response");
    }

    localStorage.setItem("access_token", data.token.access_token);
    localStorage.setItem("refresh_token", data.token.refresh_token);

    return data.token.access_token;
  } catch (err) {
    if (!isRedirecting) {
      isRedirecting = true;
      localStorage.clear();
      window.location.replace("/login");
    }
    throw err;
  }
};

const Get = (
  endPoint: string,
  payload?: {
    params?: any;
    headers?: any;
  },
) => {
  return axiosInstance.get(endPoint, payload);
};

const Post = (
  endPoint: string,
  payload?: any,
  config?: {
    params?: any;
    headers?: any;
  },
) => {
  console.log(`[API] POST request to: ${endPoint}`);
  console.log(`[API] Full URL: ${baseUrl}${endPoint}`);
  console.log(`[API] Payload:`, payload);

  const finalConfig: any = {
    ...config,
    headers: {
      ...(config?.headers || {}),
    },
  };

  // Check if payload is an instance of FormData
  if (payload instanceof FormData) {
    finalConfig.headers["Accept"] = "multipart/form-data";
  }

  return axiosInstance.post(endPoint, payload, finalConfig);
};

const Delete = (endPoint: string, _payload?: any, config?: any) => {
  return axiosInstance.delete(endPoint, config);
};

const Patch = (endPoint: string, payload?: any) => {
  return axiosInstance.patch(endPoint, payload);
};

const Put = (endPoint: string, payload: any) => {
  return axiosInstance.put(endPoint, payload);
};

// OAuth Methods
const OAuth = {
  /**
   * Fetch available OAuth providers from backend
   */
  getProviders: async (tenantId?: string): Promise<OAuthProvidersResponse> => {
    try {
      const params = tenantId ? `?tenant_id=${tenantId}` : "";
      const response = await Get(`/oauth/providers${params}`);
      return response.data;
    } catch (error) {
      console.error("Failed to fetch OAuth providers:", error);
      throw error;
    }
  },

  /**
   * Initialize OAuth flow with a provider
   */
  initializeOAuth: (
    provider: string,
    redirectUri: string,
    state: string,
  ): string => {
    const params = new URLSearchParams({
      redirect_uri: redirectUri,
      state: state,
    });

    return `${baseUrl}/oauth/internal/authorize/${provider}?${params.toString()}`;
  },

  /**
   * Handle OAuth callback and exchange token
   */
  handleCallback: async (
    provider: string,
    code: string,
    state: string,
  ): Promise<OAuthCallbackResponse> => {
    try {
      // Validate state parameter
      const storedState = sessionStorage.getItem("oauth_state");
      if (!storedState || storedState !== state) {
        throw new Error("Invalid state parameter - possible CSRF attack");
      }

      const response = await Post("/auth/oauth/callback", {
        provider,
        code,
        state,
      });

      const data = response.data;

      // Clear state from session storage
      sessionStorage.removeItem("oauth_state");

      return data;
    } catch (error) {
      console.error("OAuth callback error:", error);
      throw error;
    }
  },

  /**
   * Exchange temporary token for actual authentication tokens
   */
  exchangeToken: async (
    exchangeToken: string,
  ): Promise<TokenExchangeResponse> => {
    try {
      const response = await Post("/auth/token/exchange", {
        exchange_token: exchangeToken,
      });

      // Handle the wrapped response format
      if (response.data.result) {
        return response.data.result;
      }
      return response.data;
    } catch (error) {
      console.error("Token exchange error:", error);
      throw error;
    }
  },

  /**
   * Poll for token exchange completion
   */
  pollTokenExchange: async (
    exchangeToken: string,
    maxAttempts = 12,
    interval = 5000,
  ): Promise<TokenExchangeResponse> => {
    let attempts = 0;

    const poll = async (): Promise<TokenExchangeResponse> => {
      try {
        attempts++;
        const result = await OAuth.exchangeToken(exchangeToken);
        return result;
      } catch (error: any) {
        if (attempts >= maxAttempts) {
          throw new Error("Token exchange timeout - please try again");
        }

        // If token not ready yet, continue polling
        if (
          error.message?.includes("Token not ready") ||
          error.message?.includes("pending")
        ) {
          await new Promise((resolve) => setTimeout(resolve, interval));
          return poll();
        }

        // For other errors, throw immediately
        throw error;
      }
    };

    return poll();
  },

  /**
   * Handle OAuth error from callback
   */
  handleOAuthError: (error: string, errorDescription?: string): void => {
    console.error("OAuth error:", error, errorDescription);

    let message = "Authentication failed";

    switch (error) {
      case "access_denied":
        message = "Access was denied. Please try again.";
        break;
      case "invalid_request":
        message = "Invalid request. Please try again.";
        break;
      case "unauthorized_client":
        message = "This application is not authorized. Please contact support.";
        break;
      case "unsupported_response_type":
        message = "Unsupported authentication method.";
        break;
      case "invalid_scope":
        message = "Invalid permissions requested.";
        break;
      case "server_error":
        message = "Server error occurred. Please try again later.";
        break;
      case "temporarily_unavailable":
        message = "Service temporarily unavailable. Please try again later.";
        break;
      default:
        message =
          errorDescription || "Authentication failed. Please try again.";
    }

    errorToast(message);
  },

  /**
   * Clear OAuth session data
   */
  clearOAuthSession: (): void => {
    sessionStorage.removeItem("oauth_state");
    sessionStorage.removeItem("oauth_provider");
    sessionStorage.removeItem("oauth_exchange_token");
    // Also clear processed tokens from localStorage
    localStorage.removeItem("processed_exchange_tokens");
    localStorage.removeItem("processed_auth_codes");
  },

  /**
   * Validate OAuth provider
   */
  isValidProvider: (provider: string): boolean => {
    const validProviders = ["microsoft", "github", "google", "linkedin"];
    return validProviders.includes(provider.toLowerCase());
  },

  /**
   * Get provider display name
   */
  getProviderDisplayName: (provider: string): string => {
    const providerNames: Record<string, string> = {
      microsoft: "Microsoft",
      github: "GitHub",
      google: "Google",
      linkedin: "LinkedIn",
    };
    return providerNames[provider.toLowerCase()] || provider;
  },
};

export const AppRequest = {
  Get,
  Post,
  Put,
  Patch,
  Delete,
  OAuth,
};
