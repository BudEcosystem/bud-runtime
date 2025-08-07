import axios from "axios";
const baseUrl = process.env.NEXT_PUBLIC_BASE_URL;
import { errorToast } from "@/components/toast";

export const axiosInstance = axios.create({
  baseURL: baseUrl,
});

let Token: string | null = null;
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];
let isRedirecting = false;

if (typeof window !== "undefined") {
  Token = localStorage.getItem("access_token");
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
      config.url?.includes("auth/refresh-token");

    if (!Token && !isPublicEndpoint) {
      // Prevent redirect loop
      if (typeof window !== "undefined" && window.location.pathname !== "/login") {
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
  }
);

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onRrefreshed(token: string) {
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
          onRrefreshed(newToken);
          refreshSubscribers = [];
          return axiosInstance({
            ...err.config,
            headers: {
              ...err.config.headers,
              Authorization: `Bearer ${newToken}`,
            },
          });
        })
        .catch((refreshErr) => {
          console.error("Token refresh failed:", refreshErr);
          isRefreshing = false;
          refreshSubscribers = [];

          if (!isRedirecting) {
            isRedirecting = true;
            localStorage.clear();
            window.location.replace("/login");
          }

          return Promise.reject(refreshErr);
        });
    } else if (status === 401) {
      return new Promise((resolve) => {
        subscribeTokenRefresh((token: string) => {
          const originalRequest = err.config;
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(axiosInstance(originalRequest));
        });
      });
    } else if (status) {
      const errorMsg = err.response?.data?.message || err.response?.data?.error || err.message || "An error occurred";
      errorToast(errorMsg);
    }
    return Promise.reject(err);
  }
);

const refreshToken = async () => {
  try {
    const refreshTokenValue = localStorage.getItem("refresh_token");

    if (!refreshTokenValue) {
      throw new Error("No refresh token found");
    }

    const payload = {
      token: {
        refresh_token: refreshTokenValue,
      },
    };

    const response = await axios.post(
      `${baseUrl}/auth/refresh-token`,
      payload,
      {
        headers: {
          "Content-Type": "application/json",
        },
      }
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
  }
) => {
  return axiosInstance.get(endPoint, payload);
};

const Post = (
  endPoint: string,
  payload?: any,
  config?: {
    params?: any;
    headers?: any;
  }
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

export const AppRequest = {
  Get,
  Post,
  Put,
  Patch,
  Delete,
};
