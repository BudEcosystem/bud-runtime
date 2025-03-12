"use client";

import axios from "axios";
import { useContext } from "react";
import ChatContext from "@/app/context/ChatContext";

export function useEndPoints() {
  const { chat, endpoints, setEndpoints } = useContext(ChatContext);
  // const accessToken= localStorage.getItem('access_token')
  async function getEndPoints({ page = 1, limit = 25 }) {
    try {
      const result = await axios
        .post(
          `/api/deployments`,
          {
            page: page,
            limit: limit,
            search: false,
          },
          {
            headers: {
              Authorization: chat?.accessToken ? `Bearer ${chat?.accessToken}` : "",
              "api-key": chat?.apiKey ? chat?.apiKey : "",
            },
          }
        )
        .then((res) => {
          setEndpoints(res.data);
          return res.data;
        });

      console.log(result);
      return result;
    } catch (error) {
      return error;
    }
  }

  return { getEndPoints, endpoints };
}
