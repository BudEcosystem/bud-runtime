"use client";

import { tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext } from "react";
import ChatContext from "@/app/context/ChatContext";
import { AppRequest } from "@/app/api/requests";
import RootContext from "@/app/context/RootContext";

export function useEndPoints() {
  const { endpoints, setEndpoints } = useContext(RootContext);
  async function getEndPoints({ page = 1, limit = 25 }) {
    try {
      const result = await AppRequest.Post(`api/deployments`, {
        page: page,
        limit: limit,
        search: false,
      }).then((res) => {
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
