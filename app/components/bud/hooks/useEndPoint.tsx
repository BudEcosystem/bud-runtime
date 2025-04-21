"use client";

import { useState } from "react";
import { getEndpoints } from "@/app/lib/api";

export function useEndPoints() {
  const [endpoints, setEndpoints] = useState<any[]>([]);
  async function getEndPoints({ page = 1, limit = 25, apiKey = "", accessKey = "" }) {
    
    const result = await getEndpoints(page, limit, apiKey, accessKey);
    if (Array.isArray(result)) {
      setEndpoints(result);
      return result;
    }
    return result;
  }

  return { getEndPoints, endpoints };
}
