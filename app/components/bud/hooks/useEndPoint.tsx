"use client";

import { tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext, useState } from "react";
import { AppRequest } from "@/app/api/requests";
import RootContext from "@/app/context/RootContext";

export function useEndPoints() {
  // const [endpoints, setEndpoints] = useState<any[]>([]);
  const { setEndpoints, endpoints } = useContext(RootContext);
  async function getEndPoints({ page = 1, limit = 25, apiKey = "" }) {
    const headers: any = {
      'Content-Type': 'application/json'
    };
    if (apiKey) {
      headers["api-key"] = apiKey;
    }
    console.log(headers);
    try {
      const result = await AppRequest.Post(`api/deployments`, {
        page: page,
        limit: limit,
        search: false,
      }, {}, headers).then((res) => {
        setEndpoints(res.data);
        return res.data;
      });
      return result;
    } catch (error) {
      return error;
    }
  }

  return { getEndPoints, endpoints };
}
