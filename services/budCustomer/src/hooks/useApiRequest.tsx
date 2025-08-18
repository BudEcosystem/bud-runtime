"use client";

import { useMemo } from "react";
import { useApiConfig } from "@/components/providers/EnvironmentProvider";
import { createApiRequest } from "@/services/api/requests-new";

// Hook to create API request instance with environment configuration
export function useApiRequest() {
  const { baseUrl } = useApiConfig();

  const apiRequest = useMemo(() => {
    return createApiRequest(baseUrl);
  }, [baseUrl]);

  return apiRequest;
}

// Backward compatibility - create a singleton instance for components that can't use hooks
let globalApiRequest: ReturnType<typeof createApiRequest> | null = null;

export function getGlobalApiRequest(baseUrl?: string) {
  if (!globalApiRequest && baseUrl) {
    globalApiRequest = createApiRequest(baseUrl);
  }
  return globalApiRequest;
}
