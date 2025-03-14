"use client";
import { useContext, useEffect } from "react";
import ChatContext from "@/app/context/ChatContext";
import { AppRequest } from "@/app/api/requests";
import RootContext from "@/app/context/RootContext";
import { ActiveSession } from "../chat/HistoryList";

export const NEW_SESSION = "NEW_SESSION";

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
  request_id: string;
};

export function useMessages() {
  const { setChats, chats, sessions, setSessions } = useContext(RootContext);
  const { chat, setMessages } = useContext(ChatContext);

  async function createMessage(body: PostMessage, chatId: string) {
    console.log("Creating message", body, chatId);
    try {
      const result = await AppRequest.Post(`/api/messages`, body).then(
        (res) => {
          return res.data;
        }
      );

      console.log(result);
      const id = chat?.id;

      if (id) {
        // store to local storage
        const existing = localStorage.getItem(id);
        if (existing) {
          const data = JSON.parse(existing);
          data.push(body);
          localStorage.setItem(id, JSON.stringify(data));
        } else {
          localStorage.setItem(id, JSON.stringify([body]));
          const updatedSessions = [...sessions]?.filter(
            (session) => session.id !== NEW_SESSION
          );
          updatedSessions.push({
            id: id,
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
            name: body.prompt,
            total_tokens: body.total_tokens,
          });
          setSessions(updatedSessions);
        }

        if (chatId === NEW_SESSION) {
          // allocate new session with the id
          const updatedChats = [...chats]?.map((chat) => {
            if (chat.id === NEW_SESSION) {
              // remove the new session
              localStorage.removeItem(NEW_SESSION);
              chat.id = result.id;
            }
            return chat;
          });
          setChats(updatedChats);
        }
      }
    } catch (error) {
      console.error(error);
    }
  }

  async function getSessions() {
    // /playground/chat-sessions
    return await AppRequest.Get(`/api/sessions`).then((res) => {
      return res.data;
    });
  }

  useEffect(() => {
    const id = chat?.id;
    if (id) {
      const existing = localStorage.getItem(id);
      if (existing) {
        const data = JSON.parse(existing);
        setMessages(data);
      }
    }
  }, [chat]);

  return { createMessage, getSessions };
}
