import axios from "axios";
import { errorToast } from "@/components/toast";

// Interface for API request class initialization
interface ApiRequestConfig {
  baseUrl: string;
}

// Create a class-based approach for API requests that can be configured with environment
export class ApiRequest {
  private axiosInstance;
  private baseUrl: string;
  private isRefreshing = false;
  private refreshSubscribers: ((token: string) => void)[] = [];
  private isRedirecting = false;

  constructor(config: ApiRequestConfig) {
    this.baseUrl = config.baseUrl;
    this.axiosInstance = axios.create({
      baseURL: this.baseUrl,
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.axiosInstance.interceptors.request.use(
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
        let Token: string | null = null;
        if (typeof window !== "undefined") {
          Token = localStorage.getItem("access_token");
        }

        const isPublicEndpoint =
          config.url?.includes("auth/login") ||
          config.url?.includes("auth/register") ||
          config.url?.includes("users/reset-password") ||
          config.url?.includes("auth/refresh-token");

        if (!Token && !isPublicEndpoint) {
          // Prevent redirect loop
          if (
            typeof window !== "undefined" &&
            window.location.pathname !== "/login"
          ) {
            if (!this.isRedirecting) {
              this.isRedirecting = true;
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

    // Response interceptor
    this.axiosInstance.interceptors.response.use(
      (response) => {
        return response;
      },
      (err) => {
        const status = err?.response?.status;
        if (status === 401 && !this.isRefreshing) {
          this.isRefreshing = true;
          return this.refreshToken()
            .then((newToken) => {
              console.log("Token refresh successful");
              this.isRefreshing = false;
              this.onRefreshed(newToken);
              this.refreshSubscribers = [];
              return this.axiosInstance({
                ...err.config,
                headers: {
                  ...err.config.headers,
                  Authorization: `Bearer ${newToken}`,
                },
              });
            })
            .catch((refreshErr) => {
              console.error("Token refresh failed:", refreshErr);
              this.isRefreshing = false;
              this.refreshSubscribers = [];

              if (!this.isRedirecting) {
                this.isRedirecting = true;
                localStorage.clear();
                window.location.replace("/login");
              }

              return Promise.reject(refreshErr);
            });
        } else if (status === 401) {
          return new Promise((resolve) => {
            this.subscribeTokenRefresh((token: string) => {
              const originalRequest = err.config;
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(this.axiosInstance(originalRequest));
            });
          });
        } else if (status) {
          const errorMsg =
            err.response?.data?.message ||
            err.response?.data?.error ||
            err.message ||
            "An error occurred";
          errorToast(errorMsg);
        }
        return Promise.reject(err);
      },
    );
  }

  private subscribeTokenRefresh(cb: (token: string) => void) {
    this.refreshSubscribers.push(cb);
  }

  private onRefreshed(token: string) {
    this.refreshSubscribers.map((cb) => cb(token));
  }

  private async refreshToken() {
    try {
      const refreshTokenValue = localStorage.getItem("refresh_token");

      if (!refreshTokenValue) {
        throw new Error("No refresh token found");
      }

      const payload = {
        refresh_token: refreshTokenValue,
      };

      const response = await axios.post(
        `${this.baseUrl}/auth/refresh-token`,
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
      if (!this.isRedirecting) {
        this.isRedirecting = true;
        localStorage.clear();
        window.location.replace("/login");
      }
      throw err;
    }
  }

  Get = (
    endPoint: string,
    payload?: {
      params?: any;
      headers?: any;
    },
  ) => {
    return this.axiosInstance.get(endPoint, payload);
  };

  Post = (
    endPoint: string,
    payload?: any,
    config?: {
      params?: any;
      headers?: any;
    },
  ) => {
    console.log(`[API] POST request to: ${endPoint}`);
    console.log(`[API] Full URL: ${this.baseUrl}${endPoint}`);
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

    return this.axiosInstance.post(endPoint, payload, finalConfig);
  };

  Delete = (endPoint: string, _payload?: any, config?: any) => {
    return this.axiosInstance.delete(endPoint, config);
  };

  Patch = (endPoint: string, payload?: any) => {
    return this.axiosInstance.patch(endPoint, payload);
  };

  Put = (endPoint: string, payload: any) => {
    return this.axiosInstance.put(endPoint, payload);
  };
}

// Factory function to create API request instance with environment configuration
export function createApiRequest(baseUrl: string) {
  return new ApiRequest({ baseUrl });
}
