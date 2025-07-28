
import axios from 'axios';
const baseUrl = process.env.NEXT_PUBLIC_BASE_URL;

const apiClient = (function () {
  const URL = baseUrl;

  let instance = axios.create({
    baseURL: `${URL}`,
    headers: {
      "Content-Type": "application/json",
      // "Content-Type": "application/x-www-form-urlencoded",
    },
    // timeout: 5000,
  });

  instance.interceptors.request.use(async (config) => {
    config.headers['x-token'] = 'Nc5C00ZCyObhJuE5XDapaZH1';

    if (config.data instanceof FormData) {
      // Set 'multipart/form-data' content type for FormData requests
      config.headers['Content-Type'] = 'multipart/form-data';
    }

    return config;
  });

  return instance;
})();

export default apiClient;
