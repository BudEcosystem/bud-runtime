"use client";
import { useCallback, useEffect, useState } from "react";
import Chat from "./components/Chat";
import { Endpoint } from "./context/ChatContext";
import RootContext from "./context/RootContext";
import { ActiveSession, Session } from "./components/bud/chat/HistoryList";
import { NEW_SESSION, useMessages } from "./components/bud/hooks/useMessages";
import APIKey from "./components/APIKey";
import { useEndPoints } from "./components/bud/hooks/useEndPoint";
import { notification } from "antd";

export default function Home() {
  const [localMode, setLocalMode] = useState(false);
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
    if (!sessions || sessions?.length === 0) return;
    localStorage.setItem("sessions", JSON.stringify(sessions));
  }, [sessions]);

  // save to local storage
  useEffect(() => {
    console.log("syncing chats", chats);
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
  }, []);

  const newChatPayload = {
    id: NEW_SESSION,
    name: `New Chat`,
    settings: {
      temperature: 1,
      context_overflow: [],
      limit_response_length: true,
      min_p_sampling: 0.05,
      repeat_penalty: 0,
      sequence_length: 1000,
      stop_strings: "",
      tool_k_sampling: 40,
      top_p_sampling: 1,
    },
  };

  const closeChat = useCallback(
    async (chat: ActiveSession) => {
      const updatedChats = chats.filter((c) => c.id !== chat.id);
      if (updatedChats.length === 0) {
        updatedChats.push(newChatPayload);
      }
      setChats(updatedChats);
    },
    [chats, newChatPayload]
  );

  const createChat = useCallback(
    async (sessionId?: string, replaceChatId?: string) => {
      console.log("Creating chat");
      let updatedChats = [...chats];
      if (!sessionId) {
        if (updatedChats.find((chat) => chat.id === NEW_SESSION)) {
          alert("You can only have one new chat at a time");
          return;
        }
        updatedChats.push(newChatPayload);
      } else {
        const session = sessions.find((s) => s.id === sessionId);
        if (!session) return;
        if (replaceChatId) {
          updatedChats = updatedChats.map((chat) => {
            if (chat.id === replaceChatId) {
              return session;
            }
            return chat;
          });
        } else {
          updatedChats.push(session);
        }
      }
      setChats(updatedChats);
    },
    [chats, endpoints, sessions, newChatPayload]
  );

  useEffect(() => {
    const init = async () => {
      if (!token) return;

      localStorage.setItem("token", token);
      let localMode = false;
      if (token?.startsWith("budserve_")) {
        setLocalMode(true);
      }
      if (!localMode) {
        console.log("Getting sessions");
        const sessionsResult = await getSessions();
        setSessions(sessionsResult);
      }
      const endpointResult = await getEndPoints({ page: 1, limit: 25 });
      setTimeout(() => {
        const existing = localStorage.getItem("chats");
        if (existing) {
          const data = JSON.parse(existing);
          setChats(data);
        } else if (chats.length === 0 && endpointResult) {
          createChat();
        }
      }, 100);
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
          closeChat,
          handleDeploymentSelect,
          handleSettingsChange,
          token,
          sessions,
          setSessions,
          endpoints,
          setEndpoints,
          localMode,
        }}
      >
        {chats?.length === 0 && <APIKey />}
        <Chat />
      </RootContext.Provider>
    </main>
  );
}
