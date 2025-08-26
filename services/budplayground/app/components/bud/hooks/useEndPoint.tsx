"use client";

import { useState, useCallback } from "react";
import { getEndpoints } from "@/app/lib/api";

export function useEndPoints() {
  const [endpoints, setEndpoints] = useState<any[]>([]);

  const getEndPoints = useCallback(async ({
    page = 1,
    limit = 25,
    apiKey = "",
    accessKey = ""
  }) => {
    // Get stored values if not provided
    const storedToken = localStorage.getItem('token');
    const storedAccessKey = localStorage.getItem('access_key');
    const isJWTAuth = localStorage.getItem('is_jwt_auth') === 'true';

    // Handle JWT tokens stored in 'token' key
    if((!accessKey || accessKey === "") && storedToken && isJWTAuth) {
      // JWT is stored in token key, use it as accessKey for Authorization header
      accessKey = storedToken;
    } else if((!accessKey || accessKey === "") && storedAccessKey) {
      // Use regular access key if available
      accessKey = storedAccessKey;
    }

    // Handle API keys (budserve_ prefixed)
    if((!apiKey || apiKey === "") && storedToken && storedToken.startsWith('budserve_')) {
      apiKey = storedToken;
    }

    const result = await getEndpoints(page, limit, apiKey, accessKey);
    if (Array.isArray(result)) {
      setEndpoints(result);
      return result;
    }
    return result;
  }, []);

  return { getEndPoints, endpoints };
}
