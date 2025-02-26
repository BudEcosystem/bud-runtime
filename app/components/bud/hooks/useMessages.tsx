import { apiKey, tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext, useEffect } from "react";
import ChatContext from "@/app/context/ChatContext";

export type PostMessage = {
  prompt: string;
  response: any[];
  deployment_id: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  token_per_sec: number;
  ttft: number;
  tpot: number;
  e2e_latency: number;
  is_cache: boolean;
  chat_session_id: string;
};

export function useMessages() {
  const {
    apiKey: apiKeyState,
    token,
    setChatSessionId,
    setMessages,
  } = useContext(ChatContext);

  async function createMessage(body: PostMessage) {
    if (token) {
      const result = await axios
        .post(`${tempApiBaseUrl}/playground/messages`, body, {
          params: {},
          headers: {
            "api-key": apiKey,
          },
        })
        .then((res) => {
          console.log(res.data.endpoints);
          return res.data.endpoints;
        });

      console.log(result);
      return result;
    } else if (apiKey) {
      // store to local storage
      const existing = localStorage.getItem(apiKey);
      if (existing) {
        const data = JSON.parse(existing);
        data.push(body);
        localStorage.setItem(apiKey, JSON.stringify(data));
      } else {
        localStorage.setItem(apiKey, JSON.stringify([body]));
      }
    }
  }

  useEffect(() => {
    if (apiKey) {
      const existing = localStorage.getItem(apiKey);
      if (existing) {
        const data = JSON.parse(existing);
        setMessages(data);
      }
    }
  }, [apiKey]);

  return { createMessage };
}
