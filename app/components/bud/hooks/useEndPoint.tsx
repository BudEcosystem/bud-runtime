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
              // "authorization": `Bearer ${localStorage.getItem("access_token") ? localStorage.getItem("access_token") : `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMmUxZDYyYi1iYTk1LTQzODktOGYxZi00MGQ2ZjE4Y2Q1NDgiLCJ0eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQxMjUyODgxfQ.vFFHemLsLdou1XKA5L2JCzJ0_krmK5BPtXV_vAyOapA`}`,
              authorization: chat?.token ? `Bearer ${chat?.token}` : "",
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
