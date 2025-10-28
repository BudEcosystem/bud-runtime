"use client";

import { useState, useCallback } from "react";
import { getEndpoints } from "@/app/lib/api";
import { useAuth } from '@/app/context/AuthContext';

interface FetchParams {
  page?: number;
  limit?: number;
  apiKey?: string;
  accessKey?: string;
}

export function useEndPoints() {
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const { isSessionValid, accessToken, apiKey: sessionApiKey } = useAuth();

  const getEndPoints = useCallback(async ({
    page = 1,
    limit = 25,
    apiKey = "",
    accessKey = "",
  }: FetchParams = {}) => {
    const providedCredentials = Boolean(apiKey || accessKey);

    if (!isSessionValid && !providedCredentials) {
      return null;
    }

    const resolvedAccessKey = accessKey || accessToken || localStorage.getItem('access_token') || localStorage.getItem('token') || localStorage.getItem('access_key') || '';
    const resolvedApiKey = apiKey || sessionApiKey || (localStorage.getItem('token')?.startsWith('budserve_') ? localStorage.getItem('token') : '') || '';

    const result = await getEndpoints(page, limit, resolvedApiKey, resolvedAccessKey);
    if (Array.isArray(result)) {
      setEndpoints(result);
      return result;
    }
    return result;
  }, [isSessionValid, accessToken, sessionApiKey]);

  return { getEndPoints, endpoints, isReady: isSessionValid };
}
