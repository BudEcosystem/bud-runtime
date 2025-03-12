"use client";
import { useCallback, useEffect, useState } from "react";
import Chat from "./components/Chat";
import { Endpoint } from "./context/ChatContext";
import RootContext from "./context/RootContext";
import { ActiveSession, Session } from "./components/bud/chat/HistoryList";
import { useMessages } from "./components/bud/hooks/useMessages";
import APIKey from "./components/APIKey";
import { useEndPoints } from "./components/bud/hooks/useEndPoint";

const chatIds = ["1", "2", "3", "4", "5", "6"];

export default function Home() {
  const [_accessToken, _setAccessToken] = useState<string | null>(null);
  const [_refreshToken, _setRefreshToken] = useState<string | null>(null);
  const [_apiKey, _setApiKey] = useState<string | null>(null);
  const { getSessions } = useMessages();
  const { getEndPoints } = useEndPoints();

  const token = _apiKey || _accessToken || "";

  const [chats, setChats] = useState<ActiveSession[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);

  const createChat = useCallback(async () => {
    console.log("Creating chat");
    const updatedChats = [...chats];
    updatedChats.push({
      id: chatIds[updatedChats.length],
      name: `Chat ${updatedChats.length + 1}`,
    });
    setChats(updatedChats);
  }, [chats]);

  useEffect(() => {
    const init = () => {
      if (typeof window === "undefined") return null;

      const accessToken = window?.location.href
        ?.split("access_token=")?.[1]
        ?.split("&")[0];
      const refreshToken = window?.location.href
        ?.split("refresh_token=")?.[1]
        ?.split("&")?.[0];

      if (!accessToken || !refreshToken) return;
      _setAccessToken(accessToken);
      _setRefreshToken(refreshToken);
    };
    init();
  }, []);

  useEffect(() => {
    const apiKey = window?.location.href
      ?.split("api_key=")?.[1]
      ?.split("&")?.[0];
    if (apiKey) {
      _setApiKey(apiKey);
    }
  }, []);

  useEffect(() => {
    if (!token) return;

    localStorage.setItem("token", token);
    return getEndPoints({ page: 1, limit: 25 })
      .then(() => {
        return getSessions();
      })
      .then((res) => {
        if (chats.length === 0) {
          createChat();
        }
      });
  }, [token]);

  const handleDeploymentSelect = useCallback(
    (chat: ActiveSession, endpoint: Endpoint) => {
      if (!chat) return;
      let updatedChats = [...chats];
      console.log("updatedChats", updatedChats);
      updatedChats = updatedChats.map((_chat) => {
        if (_chat.id === chat.id) {
          console.log("Selected", _chat, chat);
          _chat.selectedDeployment = endpoint;
        }
        return _chat;
      });
      console.log("Selected", updatedChats);
      setChats(updatedChats);
    },
    [chats]
  );

  const handleSettingsChange = (
    chat: ActiveSession,
    prop: string,
    value: any
  ) => {
    let updatedChats = [...chats];
    updatedChats = updatedChats.map((item) => {
      if (item.id === chat?.id) {
        return {
          ...item,
          settings: {
            ...item.settings,
            [prop]: value,
          } as any,
        };
      }
      return item;
    });
    setChats(updatedChats);
  };

  return (
    <main className="flex flex-col gap-8 row-start-2 items-center w-full h-[100vh] p-4">
      <RootContext.Provider
        value={{
          chats,
          setChats,
          createChat,
          handleDeploymentSelect,
          handleSettingsChange,
          token,
          sessions,
          setSessions,
        }}
      >
        {chats?.length === 0 && <APIKey />}
        <Chat />
      </RootContext.Provider>
    </main>
  );
}
