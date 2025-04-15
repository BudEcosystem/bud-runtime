"use client";

import { useState } from "react";
import { getEndpoints } from "@/app/lib/api";

export function useEndPoints() {
  const [endpoints, setEndpoints] = useState<any[]>([]);
  async function getEndPoints({ page = 1, limit = 25, apiKey = "" }) {
    
    const result = await getEndpoints(page, limit, apiKey);
    if (Array.isArray(result)) {
      setEndpoints(result);
      return result;
    }
    return [];
  }

  return { getEndPoints, endpoints };
}
