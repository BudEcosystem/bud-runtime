"use client";
import { useContext, useEffect } from "react";
import ChatContext from "@/app/context/ChatContext";
import { AppRequest } from "@/app/api/requests";
import RootContext from "@/app/context/RootContext";

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
  const { setSessions } = useContext(RootContext);
  const { chat, setMessages } = useContext(ChatContext);
  const id = chat?.id;

  async function createMessage(body: PostMessage) {
    try {
      const result = await AppRequest.Post(`/api/messages`, body).then(
        (res) => {
          return res.data;
        }
      );

      console.log(result);

      if (id) {
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

  async function createSession(deploymentId: string) {
    try {
      const body: PostMessage = {
        prompt: "Create session",
        response: "Session created",
        deployment_id: deploymentId,
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
        token_per_sec: 0,
        ttft: 0,
        tpot: 0,
        e2e_latency: 0,
        is_cache: false,
      };
      const result = await AppRequest.Post(`/api/messages`).then((res) => {
        return res.data;
      });
      if (id) {
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
    return await AppRequest.Get(`/api/sessions`)
      .then((res) => {
        return res.data;
      })
      .then((res) => {
        console.log(res);
        setSessions(res);
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

  return { createMessage, getSessions, createSession };
}
