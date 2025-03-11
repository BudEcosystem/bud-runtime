"use client";
import { tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext, useEffect } from "react";
import ChatContext from "@/app/context/ChatContext";

export type PostMessage = {
  prompt: string;
  response: any;
  deployment_id: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  token_per_sec: number;
  ttft: number;
  tpot: number;
  e2e_latency: number;
  is_cache: boolean;
  chat_session_id?: string;
  request_id?: string;
};

export function useMessages() {
  const { chat, token, setMessages } = useContext(ChatContext);
  const apiKey = chat?.apiKey;
  const id = chat?.id;

  async function createMessage(body: PostMessage) {
    try {
      if (apiKey) {
        const result = await axios
          .post(`${tempApiBaseUrl}/playground/messages`, body, {
            params: {},
            headers: {
              Authorization: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMmUxZDYyYi1iYTk1LTQzODktOGYxZi00MGQ2ZjE4Y2Q1NDgiLCJ0eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQxNjkxNjAxfQ.-W1JatgUZ1zkQOjhCrSVcK_8oojWN0GOcN5_X9uhAfY`,
              "api-key": apiKey,
            },
          })
          .then((res) => {
            console.log(res.data.endpoints);
            return res.data.endpoints;
          });
  
        console.log(result);
        return result;
      } else if (apiKey && id) {
        // store to local storage
        const existing = localStorage.getItem(id);
        if (existing) {
          const data = JSON.parse(existing);
          data.push(body);
          localStorage.setItem(id, JSON.stringify(data));
        } else {
          localStorage.setItem(id, JSON.stringify([body]));
        }
      }
    } catch (error) {
      console.error(error);
    } 
  }

  async function getSessions() {
    // /playground/chat-sessions

    return await axios
      .get(`${tempApiBaseUrl}/playground/chat-sessions`, {
        params: {},
        headers: {
          Authorization: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkMmUxZDYyYi1iYTk1LTQzODktOGYxZi00MGQ2ZjE4Y2Q1NDgiLCJ0eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQxNjg5NzU5fQ.NXvJtLl6U9ckW_wQjHRrNJ9DtRjC1laBFfgpsnRo_Ts`,
          "api-key": apiKey,
        },
      })
      .then((res) => {
        return res.data.chat_sessions;
      });
  }

  useEffect(() => {
    if (id) {
      const existing = localStorage.getItem(id);
      if (existing) {
        const data = JSON.parse(existing);
        setMessages(data);
      }
    }
  }, [id]);

  return { createMessage, getSessions };
}
