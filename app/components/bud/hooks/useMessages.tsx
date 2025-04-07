"use client";
import { useContext, useEffect } from "react";
import ChatContext from "@/app/context/ChatContext";
import { AppRequest } from "@/app/api/requests";
import RootContext from "@/app/context/RootContext";
import { ActiveSession, ChatSettings } from "../chat/HistoryList";
import { Message, useChat } from "@ai-sdk/react";
import { tempApiBaseUrl } from "../environment";

export const NEW_SESSION = "NEW_SESSION";

export type Usage = {
  completionTokens: number;
  promptTokens: number;
  totalTokens: number;
};

export type Response = {
  message: Message;
  usage: Usage;
};

export type Metrics = {
  e2e_latency: number;
  throughput: number;
  ttft: number;
  itl: number;
}

export type PostMessage = {
  prompt: string;
  response: Response;
  deployment_id: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  is_cache: boolean;
  chat_session_id?: string;
  request_id: string;
  name?: string;
  metrics?: Metrics;
  annotations?: any;
  id: string;
};

export function useMessages() {
  const { setChats, chats, sessions, setSessions, localMode } =
    useContext(RootContext);
  const { chat, setMessages } = useContext(ChatContext);

  async function createSetting(settings: ChatSettings) {
    try {
      const result = await AppRequest.Post(
        `${tempApiBaseUrl}/playground/chat-settings`,
        settings
      ).then((res) => {
        return res.data?.chat_setting;
      });

      console.log(`Setting created: ${result.id}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  }

  async function updateSetting(settings: ChatSettings) {
    try {
      const result = await AppRequest.Patch(
        `${tempApiBaseUrl}/playground/chat-settings/${settings.id}`,
        settings
      ).then((res) => {
        return res.data?.chat_setting;
      });

      console.log(`Setting updated: ${result.id}`);
      return result.id;
    } catch (error) {
      console.error(error);
    }
  }

  async function createMessage(body: PostMessage, chatId: string) {
    console.log("Creating message", body, chatId);
    let updatedChats = [...chats];
    try {
      const result = await AppRequest.Post(`/api/messages`, body).then(
        (res) => {
          return res.data;
        }
      );

      console.log(`Message created: ${result.chat_session_id}`);
      const sessionId = result?.chat_session_id;

      // save settings to local storage

      if (chat?.chat_setting) {
        if (localMode) {
          localStorage.setItem(
            `settings-${sessionId}`,
            JSON.stringify(chat?.chat_setting)
          );
        } else if (!body.chat_session_id) {
          const settings = await createSetting(chat?.chat_setting);
          console.log(`Setting created: ${settings}`);
          updatedChats = [...chats]?.map((chat) => {
            if (chat.id === NEW_SESSION) {
              chat.chat_setting = settings;
            }
            return chat;
          });
        } else {
          const settings = await updateSetting(chat?.chat_setting);
          console.log(`Setting updated: ${settings}`);
        }
      }

      if (sessionId) {
        // store to local storage
        const existing = localStorage.getItem(sessionId);
        if (existing) {
          const data = JSON.parse(existing);
          data.push(body);
          localStorage.setItem(sessionId, JSON.stringify(data));
        } else {
          localStorage.setItem(sessionId, JSON.stringify([body]));
          const updatedSessions = [...sessions]?.filter(
            (session) => session.id !== NEW_SESSION
          );
          updatedSessions.push({
            id: sessionId,
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
            name: body.prompt,
            total_tokens: body.total_tokens,
          });
          setSessions(updatedSessions);
        }

        if (chatId === NEW_SESSION) {
          // allocate new session with the id
          updatedChats = [...chats]?.map((chat) => {
            if (chat.id === NEW_SESSION) {
              // remove the new session
              localStorage.removeItem(NEW_SESSION);
              chat.id = sessionId;
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

  async function getSessionMessages(id: string) {
    // /playground/chat-sessions
    return await AppRequest.Get(`/api/sessions/${id}`).then((res) => {
      return res.data;
    });
  }

  async function deleteSession(id: string) {
    return await AppRequest.Delete(`${tempApiBaseUrl}/playground/chat-sessions/${id}`).then((res) => {
      return res.data;
    });
  }

  return { createMessage, getSessions, getSessionMessages, deleteSession };
}
