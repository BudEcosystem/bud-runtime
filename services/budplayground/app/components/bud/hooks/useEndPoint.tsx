"use client";

import { useState, useCallback } from "react";
import { getEndpoints } from "@/app/lib/api";
import { useAuthContext } from '@/app/context/AuthContext';

interface FetchParams {
  page?: number;
  limit?: number;
  apiKey?: string;
  accessKey?: string;
}

export function useEndPoints() {
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const auth = useAuthContext();
  const isSessionValid = auth?.isSessionValid ?? false;

  const getEndPoints = useCallback(async ({
    page = 1,
    limit = 25,
    apiKey = "",
    accessKey = "",
  }: FetchParams = {}) => {
    const providedCredentials = Boolean(apiKey || accessKey);

    // Resolve tokens first
    const resolvedAccessKey =
      accessKey ||
      auth?.accessToken ||
      (typeof window !== 'undefined' ?
        (localStorage.getItem('access_token') || localStorage.getItem('token') || localStorage.getItem('access_key') || '') :
        '');

    const resolvedApiKey =
      apiKey ||
      auth?.apiKey ||
      (typeof window !== 'undefined'
        ? (localStorage.getItem('token')?.startsWith('budserve_') ? localStorage.getItem('token') : '') || ''
        : '');

    // Check if we have valid credentials to proceed
    const hasResolvedCredentials = Boolean(resolvedAccessKey || resolvedApiKey);

    if (!isSessionValid && !providedCredentials && !hasResolvedCredentials) {
      return null;
    }

    const result = await getEndpoints(page, limit, resolvedApiKey, resolvedAccessKey);
    if (Array.isArray(result)) {
      setEndpoints(result);
      return result;
    }
    return result;
  }, [isSessionValid, auth?.accessToken, auth?.apiKey]);

  // Only consider ready when we have a valid session AND actual tokens to use
  const hasTokens = Boolean(auth?.accessToken || auth?.apiKey);
  const isReady = (auth?.isSessionValid && hasTokens) ?? false;

  return { getEndPoints, endpoints, isReady };
}
