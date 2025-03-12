import axios from "axios";

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

// Response interceptor
axiosInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  (err) => {
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
