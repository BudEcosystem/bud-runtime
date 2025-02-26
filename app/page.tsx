"use client";

import Chat from "./components/bud/chat/Chat";
import { useState } from "react";
import RootContext from "./context/RootContext";
import { Endpoint } from "./context/ChatContext";

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
  "budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
  "budserve_tYak6eMumQTwZ60IsZSa5RQa3WafUSPeG5CHHEgl",
];

export default function Page() {
  const [chats, setChats] = useState<ChatType[]>([]);

  const createChat = () => {
    const updatedChats = [...chats];
    updatedChats.push({
      id: Math.random().toString(36).substring(7),
      apiKey: apiKeyList[updatedChats.length],
      token: "",
      chatSessionId:  Math.random().toString(36).substring(7),
      selectedDeployment : null,
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
  };

  return (
    <RootContext.Provider value={{ chats, setChats, createChat }}>
      <Chat />
    </RootContext.Provider>
  );
}
