import axios from "axios";
const baseUrl = process.env.NEXT_PUBLIC_BASE_URL;
import { errorToast } from "./../../components/toast";
import router from "next/router";

export const axiosInstance = axios.create({
  baseURL: baseUrl,
});

let Token = null;
let isRefreshing = false;
let refreshSubscribers = [];
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
      config.url?.includes("users/reset-password") ||
      config.url?.includes("auth/refresh-token");

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
        subscribeTokenRefresh((newToken) => {
          err.config.headers.Authorization = `Bearer ${newToken}`;
          resolve(axiosInstance(err.config));
        });
      });
    }
    return handleErrorResponse(err);
  },
);

const handleErrorResponse = (err) => {
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
    if (err && localStorage.getItem("access_token")) {
      console.log(err.response?.data?.message);
      errorToast(err.response?.data?.message);
    }
    return false;
  }
};

const onRrefreshed = (token) => {
  refreshSubscribers.map((callback) => callback(token));
};

const subscribeTokenRefresh = (callback) => {
  refreshSubscribers.push(callback);
};

const refreshToken = async () => {
  try {
    const response = await axiosInstance.post("auth/refresh-token", {
      refresh_token: localStorage.getItem("refresh_token"),
    });

    const data = response?.data;

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
  endPoint,
  payload?: {
    params?: any;
    headers?: any;
  },
) => {
  return axiosInstance.get(endPoint, payload);
};

const Post = (
  endPoint,
  payload?: any,
  config?: {
    params?: any;
    headers?: any;
  },
) => {
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

const Delete = (endPoint, payload?, config?) => {
  return axiosInstance.delete(endPoint, config);
};

const Patch = (endPoint, payload?) => {
  return axiosInstance.patch(endPoint, payload);
};

const Put = (
  endPoint,
  payload?: any,
  config?: {
    params?: any;
    headers?: any;
  },
) => {
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

  return axiosInstance.put(endPoint, payload, finalConfig);
};

export const AppRequest = {
  Get,
  Post,
  Put,
  Patch,
  Delete,
};
