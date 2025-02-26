"use client";

import Chat from "./components/bud/chat/Chat";
import { useState } from "react";
import RootContext from "./context/RootContext";

export type ChatType = {
  apiKey: string;
  token: string;
  chatSessionId: string;
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
      apiKey: apiKeyList[updatedChats.length],
      token: "",
      chatSessionId: "",
    });
    setChats(updatedChats);
  };

  return (
    <RootContext.Provider value={{ chats, setChats, createChat }}>
      <Chat />
    </RootContext.Provider>
  );
}
