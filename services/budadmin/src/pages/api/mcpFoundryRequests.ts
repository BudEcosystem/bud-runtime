import axios from "axios";
import { mcpFoundryUrl, mcpFoundryToken } from "@/components/environment";
import { errorToast } from "@/components/toast";
import {
  isRefreshing,
  isRedirecting,
  setIsRefreshing,
  setIsRedirecting,
  refreshSubscribers,
  clearRefreshSubscribers,
  onRrefreshed,
  subscribeTokenRefresh,
  refreshToken,
} from "./requests";

const serializeParams = (params?: Record<string, any>) => {
  if (!params) {
    return "";
  }

  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null) {
          searchParams.append(key, String(item));
        }
      });
      return;
    }

    if (typeof value === "object") {
      Object.entries(value).forEach(([nestedKey, nestedValue]) => {
        if (nestedValue !== undefined && nestedValue !== null) {
          searchParams.append(`${key}.${nestedKey}`, String(nestedValue));
        }
      });
      return;
    }

    searchParams.append(key, String(value));
  });

  return searchParams.toString();
};

export const mcpFoundryAxiosInstance = axios.create({
  baseURL: mcpFoundryUrl,
});

mcpFoundryAxiosInstance.defaults.paramsSerializer = {
  serialize: serializeParams,
};

// Get token - prioritize env token (for development), fallback to localStorage
const getToken = (): string | null => {
  // Use configured token from env if available (temporary for dev)
  if (mcpFoundryToken) {
    return mcpFoundryToken;
  }
  // Otherwise use localStorage token
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token");
  }
  return null;
};

// Request interceptor
mcpFoundryAxiosInstance.interceptors.request.use(
  async (config) => {
    // Check Internet Connection
    if (typeof window !== "undefined" && !navigator.onLine) {
      errorToast("No internet connection");
      return Promise.reject(new Error("No internet connection"));
    }

    // Network quality check
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

    // Get token (env token takes priority over localStorage)
    const token = getToken();

    // If using env token, skip auth redirect logic
    if (mcpFoundryToken) {
      if (config.headers) {
        config.headers.Authorization = `Bearer ${mcpFoundryToken}`;
      }
      return config;
    }

    // Standard auth flow for localStorage token
    if (!token) {
      if (
        typeof window !== "undefined" &&
        window.location.pathname !== "/login" &&
        window.location.pathname !== "/reset-password" &&
        window.location.pathname !== "/auth/reset-password"
      ) {
        if (!isRedirecting) {
          setIsRedirecting(true);
          localStorage.clear();
          window.location.replace("/login");
        }
      }
      return Promise.reject(new Error("No access token found"));
    }

    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
mcpFoundryAxiosInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  (err) => {
    const status = err?.response?.status;

    // If using env token, skip token refresh logic - just handle error
    if (mcpFoundryToken) {
      return handleMcpFoundryErrorResponse(err);
    }

    // Standard token refresh flow for localStorage token
    if (status === 401 && !isRefreshing) {
      setIsRefreshing(true);
      return refreshToken()
        .then((newToken) => {
          console.log("Token refresh successful (MCP Foundry)");
          setIsRefreshing(false);
          onRrefreshed(newToken);
          clearRefreshSubscribers();
          return mcpFoundryAxiosInstance({
            ...err.config,
            headers: {
              ...err.config.headers,
              Authorization: `Bearer ${newToken}`,
            },
          });
        })
        .catch((refreshErr) => {
          console.log("Token refresh failed (MCP Foundry)", refreshErr);
          setIsRefreshing(false);
          clearRefreshSubscribers();
          if (!isRedirecting) {
            return Promise.reject(refreshErr);
          }
          return new Promise(() => {});
        });
    } else if (status === 401 && isRefreshing) {
      return new Promise((resolve) => {
        subscribeTokenRefresh((newToken: string) => {
          err.config.headers.Authorization = `Bearer ${newToken}`;
          resolve(mcpFoundryAxiosInstance(err.config));
        });
      });
    }

    return handleMcpFoundryErrorResponse(err);
  }
);

const handleMcpFoundryErrorResponse = (err: any) => {
  // If using env token, don't redirect on 401 - just reject
  if (err.response && err.response.status === 401) {
    if (mcpFoundryToken) {
      errorToast("MCP Foundry token is invalid or expired");
      return Promise.reject(err);
    }
    if (!isRedirecting) {
      setIsRedirecting(true);
      localStorage.clear();
      window.location.replace("/login");
    }
    return false;
  }

  if (err.response && err.response.status === 403) {
    errorToast(err.response?.data?.message || err.response?.data?.detail || "Forbidden");
    return false;
  }

  if (err.response && err.response.status === 500) {
    return Promise.reject(err);
  }

  if (err.response && err.response.status === 422) {
    return Promise.reject(err);
  }

  if (err.response && err.response.status === 404) {
    return Promise.reject(err);
  }

  if (err && localStorage.getItem("access_token")) {
    const errorMessage = err.response?.data?.detail || err.response?.data?.message;
    if (errorMessage) {
      errorToast(errorMessage);
    }
  }

  return Promise.reject(err);
};

const Get = (
  endPoint: string,
  payload?: {
    params?: any;
    headers?: any;
  }
) => {
  return mcpFoundryAxiosInstance.get(endPoint, payload);
};

const Post = (
  endPoint: string,
  payload?: any,
  config?: {
    params?: any;
    headers?: any;
  }
) => {
  const finalConfig: any = {
    ...config,
    headers: {
      ...(config?.headers || {}),
    },
  };

  if (payload instanceof FormData) {
    finalConfig.headers["Accept"] = "multipart/form-data";
  }

  return mcpFoundryAxiosInstance.post(endPoint, payload, finalConfig);
};

const Delete = (endPoint: string, payload?: any, config?: any) => {
  return mcpFoundryAxiosInstance.delete(endPoint, config);
};

const Patch = (endPoint: string, payload?: any) => {
  return mcpFoundryAxiosInstance.patch(endPoint, payload);
};

const Put = (
  endPoint: string,
  payload?: any,
  config?: {
    params?: any;
    headers?: any;
  }
) => {
  const finalConfig: any = {
    ...config,
    headers: {
      ...(config?.headers || {}),
    },
  };

  if (payload instanceof FormData) {
    finalConfig.headers["Accept"] = "multipart/form-data";
  }

  return mcpFoundryAxiosInstance.put(endPoint, payload, finalConfig);
};

export const McpFoundryRequest = {
  Get,
  Post,
  Put,
  Patch,
  Delete,
};
