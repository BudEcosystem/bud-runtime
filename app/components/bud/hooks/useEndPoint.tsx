"use client";

import { tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext } from "react";
import ChatContext from "@/app/context/ChatContext";
import { AppRequest } from "@/app/api/requests";

export function useEndPoints() {
  const { chat, endpoints, setEndpoints } = useContext(ChatContext);
  // const accessToken= localStorage.getItem('access_token')
  async function getEndPoints({ page = 1, limit = 25 }) {
    try {
      const result = await AppRequest.Get(
        `${tempApiBaseUrl}/playground/deployments`,
        {
          params: {
            page: page,
            limit: limit,
            search: false,
          },
        }
      ).then((res) => {
        console.log(res.data.endpoints);
        setEndpoints(res.data.endpoints);
        return res.data.endpoints;
      });

      console.log(result);
      return result;
    } catch (error) {
      return error;
    }
  }

  return { getEndPoints, endpoints };
}
