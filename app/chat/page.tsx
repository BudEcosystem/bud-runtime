"use client";

import { useEffect, useState } from "react";
import { v4 as uuidv4 } from 'uuid';
import { useLoader } from "../context/LoaderContext";

import { useChatStore } from "../store/chat";
import { Session } from "../types/chat";
import ChatWindow from "./components/ChatWindow";

export default function ChatPage() {
  const { activeChatList, createChat } = useChatStore();
  const { hideLoader } = useLoader();

  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      // Access persisted store only on client
      const hydrated = useChatStore.persist?.hasHydrated?.() ?? false;
      setHasHydrated(hydrated);
    }
  }, []);
  

  useEffect(() => {
    console.log('Hydration state:', hasHydrated);
    console.log('Active chat list:', activeChatList);

    if (!hasHydrated) return;
    
    hideLoader();
    if (activeChatList.length === 0) {
      createNewChat();
    }
  }, [hasHydrated]);

  useEffect(() => {
    hideLoader();
  }, []);

  const createNewChat = () => {
    const newChatPayload = {
      id: uuidv4(),
      name: `New Chat`,
      chat_setting_id: "default",
      created_at: new Date().toISOString(),
      modified_at: new Date().toISOString(),
      total_tokens: 0,
      active: true,
    };
    createChat(newChatPayload);

  }

  return (
    <div
      className="w-full h-full transition-all duration-300 flex size-full overflow-x-auto snap-x snap-mandatory md:snap-none md:overflow-y-hidden"
      style={
        activeChatList?.length > 0
          ? {}
          : {
            position: "absolute",
            top: 0,
            left: -5000,
            zIndex: -1,
          }
      }
    >
      {activeChatList.map((chat: Session, index: number) => (
          chat.active && <ChatWindow key={index} chat={chat} />
      ))}
    </div>
  )
}
