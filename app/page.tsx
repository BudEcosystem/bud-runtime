"use client";
import { useCallback, useEffect, useState } from "react";
import Chat from "./components/Chat";
import { Endpoint } from "./context/ChatContext";
import RootContext from "./context/RootContext";
import { useSearchParams } from "next/navigation";

export type ChatSettings = {
  temperature: number;
  limit_response_length: boolean;
  sequence_length: number;
  context_overflow: string[];
  stop_strings: string;
  tool_k_sampling: number;
  repeat_penalty: number;
  top_p_sampling: number;
  min_p_sampling: number;
};

export type ChatType = {
  id: string;
  apiKey: string;
  token: string;
  chatSessionId: string;
  settings: ChatSettings;
  selectedDeployment: Endpoint | null;
};

const apiKeyList = [
  "budserve_NgMnHOzyQjCXGgmoFZrYNwS7LgqZU2VMcmz3bz4U",
  "1budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "3budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "4budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "5budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "7budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
];

const chatIds = ["1", "2", "3", "4", "5", "6"];

const chatSessionIds = ["1", "2", "3", "4", "5", "6"];

const initialChat = {
  id: chatIds[0],
  apiKey: apiKeyList[0],
  token: "",
  chatSessionId: chatSessionIds[0],
  selectedDeployment: null,
  settings: {
    temperature: 0.7,
    limit_response_length: false,
    sequence_length: 256,
    context_overflow: [],
    stop_strings: "",
    tool_k_sampling: 0.7,
    repeat_penalty: 1.0,
    top_p_sampling: 0.9,
    min_p_sampling: 0.0,
  },
};

export default function Home() {
  const searchParams = useSearchParams();
  const accessToken = searchParams.get("access_token");
  const refreshToken = searchParams.get("refresh_token");

  const [chats, setChats] = useState<ChatType[]>([initialChat]);

  const createChat = useCallback(() => {
    const updatedChats = [...chats];
    updatedChats.push({
      id: chatIds[updatedChats.length],
      apiKey: apiKeyList[updatedChats.length],
      token: "",
      chatSessionId: chatSessionIds[updatedChats.length],
      selectedDeployment: null,
      settings: {
        temperature: 0.7,
        limit_response_length: false,
        sequence_length: 256,
        context_overflow: [],
        stop_strings: "",
        tool_k_sampling: 0.7,
        repeat_penalty: 1.0,
        top_p_sampling: 0.9,
        min_p_sampling: 0.0,
      },
    });
    setChats(updatedChats);
  }, [chats, accessToken, refreshToken]);

  const handleDeploymentSelect = useCallback(
    (chat: ChatType, endpoint: Endpoint) => {
      if (!chat) return;
      let updatedChats = [...chats];
      console.log("updatedChats", updatedChats);
      updatedChats = updatedChats.map((_chat) => {
        if (_chat.id === chat.id) {
          console.log("Selected", _chat, chat);
          _chat.selectedDeployment = endpoint;
          _chat.settings = {
            ..._chat.settings,
          };
        }
        return _chat;
      });
      console.log("Selected", updatedChats);
      setChats(updatedChats);
    },
    [chats]
  );

  const handleSettingsChange = (chat: ChatType, prop: string, value: any) => {
    let updatedChats = [...chats];
    updatedChats = updatedChats.map((item) => {
      if (item.id === chat?.id) {
        return {
          ...item,
          settings: {
            ...item.settings,
            [prop]: value,
          },
        };
      }
      return item;
    });
    setChats(updatedChats);
  };

  useEffect(() => {
    if (!accessToken || !refreshToken) return;
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
  }, [accessToken, refreshToken]);

  return (
    <main className="flex flex-col gap-8 row-start-2 items-center w-full h-[100vh] p-4">
      <RootContext.Provider
        value={{
          chats,
          setChats,
          createChat,
          handleDeploymentSelect,
          handleSettingsChange,
        }}
      >
        <Chat />
      </RootContext.Provider>
    </main>
  );
}
