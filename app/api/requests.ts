import axios from "axios";
import { apiBaseUrl } from "../components/bud/environment";

export const axiosInstance = axios.create({
});

let Token: any = null;
let isRefreshing = false;
let refreshSubscribers: any = [];

if (typeof window !== "undefined") {
  Token = localStorage.getItem("token");
}

// Request interceptor
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (config.headers) {
      if (token?.startsWith('budserve_')) {
        config.headers['api-key'] = token;
      } else {
        config.headers.Authorization = token ? `Bearer ${token}` : "";
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

const onRrefreshed = (token: string) => {
  refreshSubscribers.map((callback: any) => callback(token));
};

const subscribeTokenRefresh = (callback: any) => {
  refreshSubscribers.push(callback);
};

const refreshToken = async () => {
  try {
    const response = await axiosInstance.post(`${apiBaseUrl}/token/refresh`, {
      refresh_token: localStorage.getItem("refresh_token"),
    });
    const data = response.data;
    if (!data?.result) {
      localStorage.clear();
      return Promise.reject(data);
    }
    localStorage.setItem("access_token", data.result.access_token);
    localStorage.setItem("refresh_token", data.result.refresh_token);
    return data.result.access_token;
  } catch (error) {
    // errorToast(error?.response?.data?.error?.message || "Unauthorized Access");
    localStorage.clear();
    return Promise.reject(error);
  }
};


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
          isRefreshing = false;
          onRrefreshed(newToken);
          refreshSubscribers = [];
          return axiosInstance(err.config);
        })
        .catch((error) => {
          isRefreshing = false;
          refreshSubscribers = [];
          return Promise.reject(error);
        });
    } else if (status === 401 && isRefreshing) {
      return new Promise((resolve) => {
        subscribeTokenRefresh((newToken: string) => {
          err.config.headers.Authorization = `Bearer ${newToken}`;
          resolve(axiosInstance(err.config));
        });
      });
    }
    return handleErrorResponse(err);
  }
);

const handleErrorResponse = (err: any) => {
  if (err.response && err.response.status === 403) {
    return false;
  } else if (err.response && err.response.code === 500) {
    return false;
  } else if (err.response && err.response.status === 422) {
    return false;
  } else {
    return false;
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

const Post = (endPoint: string, payload?: any, params?: any) => {
  const config: any = {
    params: params,
  };
  // Check if payload is an instance of FormData
  if (payload instanceof FormData) {
    config["headers"] = {
      Accept: "multipart/form-data",
    };
  }

  return axiosInstance.post(endPoint, payload, config);
};

const Delete = (endPoint: string, payload?: any) => {
  return axiosInstance.delete(endPoint);
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
