"use client";
import { useCallback, useEffect, useState } from "react";
import Chat from "./components/Chat";
import { Endpoint } from "./context/ChatContext";
import RootContext from "./context/RootContext";
import { ActiveSession, Session } from "./components/bud/chat/HistoryList";
import { NEW_SESSION, useMessages } from "./components/bud/hooks/useMessages";
import APIKey from "./components/APIKey";
import { useEndPoints } from "./components/bud/hooks/useEndPoint";

export default function Home() {
  const [_accessToken, _setAccessToken] = useState<string | null>(null);
  const [_refreshToken, _setRefreshToken] = useState<string | null>(null);
  const [_apiKey, _setApiKey] = useState<string | null>(null);
  const { getSessions } = useMessages();
  const { getEndPoints } = useEndPoints();
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);

  const token = _apiKey || _accessToken || "";

  const [chats, setChats] = useState<ActiveSession[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);

  useEffect(() => {
    const existing = localStorage.getItem("sessions");
    if (existing) {
      const data = JSON.parse(existing);
      setSessions(data);
    }
  }, []);

  // save to local storage
  useEffect(() => {
    if (sessions.length === 0) return;
    localStorage.setItem("sessions", JSON.stringify(sessions));
  }, [sessions]);

  // save to local storage
  useEffect(() => {
    console.log('syncing chats', chats);
    const validChats = chats.filter((chat) => chat.id !== NEW_SESSION);
    if (validChats?.length === 0) return;
    localStorage.setItem("chats", JSON.stringify(validChats));
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
      const _apiKey = window?.location.href
        ?.split("api_key=")?.[1]
        ?.split("&")?.[0];
      if (_apiKey) {
        _setApiKey(_apiKey);
      }

      if (accessToken && refreshToken) {
        _setAccessToken(accessToken);
        _setRefreshToken(refreshToken);
      }
    };
    init();
  }, [window?.location.href]);

  const createChat = useCallback(
    async (sessionId?: string) => {
      console.log("Creating chat");
      const updatedChats = [...chats];
      if (!sessionId) {
        if (updatedChats.find((chat) => chat.id === NEW_SESSION)) return;
        updatedChats.push({
          id: NEW_SESSION,
          name: `Chat ${updatedChats.length + 1}`,
        });
      }else{
        const session = sessions.find((s) => s.id === sessionId);
        if (!session) return;
        updatedChats.push(session);
      }
      setChats(updatedChats);
    },
    [chats, endpoints, sessions]
  );

  useEffect(() => {
    const init = () => {
      if (!token) return;

      localStorage.setItem("token", token);
      return getSessions()
        .then((result) => {
          if (result?.length > 0) {
            setSessions(result);
          }
          return getEndPoints({ page: 1, limit: 25 });
        })
        .then((res) => {
          setTimeout(() => {
            const existing = localStorage.getItem("chats");
            if (existing) {
              const data = JSON.parse(existing);
              setChats(data);
            } else if (chats.length === 0 && res) {
              createChat();
            }
          }, 100);
        });
    };
    init();
  }, [token]);

  const handleDeploymentSelect = useCallback(
    (chat: ActiveSession, endpoint: Endpoint) => {
      if (!chat) return;
      let updatedChats = [...chats];
      updatedChats = updatedChats.map((_chat) => {
        if (_chat.id === chat.id) {
          _chat.selectedDeployment = endpoint;
        }
        return _chat;
      });
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
          endpoints,
          setEndpoints,
        }}
      >
        {chats?.length === 0 && <APIKey />}
        <Chat />
      </RootContext.Provider>
    </main>
  );
}
