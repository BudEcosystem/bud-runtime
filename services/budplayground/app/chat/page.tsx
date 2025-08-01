"use client";

import { useEffect, useState } from "react";
import { v4 as uuidv4 } from 'uuid';
import { useLoader } from "../context/LoaderContext";
import { useRouter } from 'next/navigation';

import { useChatStore } from "../store/chat";
import { Session } from "../types/chat";
import ChatWindow from "./components/ChatWindow";
import { useAuth } from "../context/AuthContext";
import { Endpoint } from "../types/deployment";

export default function ChatPage() {
  const { activeChatList, createChat } = useChatStore();
  const { hideLoader } = useLoader();
  const { apiKey, login } = useAuth();
  const router = useRouter();

  const [hasHydrated, setHasHydrated] = useState(false);
  const [isSingleChat, setIsSingleChat] = useState(false);
  const [selectedModel, setSelectedModel] = useState("");

  const checkAccessKey = async (accessKey: string) => {
    const isLoginSuccessful = await login("", accessKey);
    if(isLoginSuccessful) {
      console.log('Login successful');
      // router.replace(`chat`);
    } else {
      // setIsInvalidApiKey(true);
      router.replace(`login`);
    }
  }

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
    if (selectedModel) {
      // Define the type for selectedDeployment
      const selectedDeployment: Endpoint = {
        name: selectedModel,
        id: "default",
        status: "running",
        model: "default",
        project: null,
        created_at: new Date().toISOString()
      };
      // Add the property to newChatPayload
      (newChatPayload as any).selectedDeployment = selectedDeployment;
    }
    createChat(newChatPayload);

  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      // Access persisted store only on client
      const hydrated = useChatStore.persist?.hasHydrated?.() ?? false;
      setHasHydrated(hydrated);
    }
  }, []);


  useEffect(() => {
    if (!hasHydrated) return;

    hideLoader();
    if (activeChatList.length === 0) {
      createNewChat();
    }
  }, [hasHydrated, activeChatList.length, createNewChat, hideLoader]);

  useEffect(() => {

    const params = new URLSearchParams(window.location.search);
    const accessKey = params.get('access_token');
    const isSingleChat = params.get('is_single_chat');
    const model = params.get('model');
    const baseUrl = params.get('base_url');
    if(accessKey) {
      checkAccessKey(accessKey);
    } else {
      hideLoader();
    }
    if(isSingleChat == "true") {
      setIsSingleChat(true);
    }
    if(model) {
      setSelectedModel(model);
    }

  }, [checkAccessKey, hideLoader]);

  return (
    <div
      className={`w-full h-full transition-all duration-300 flex size-full overflow-x-auto snap-x snap-mandatory md:snap-none md:overflow-y-hidden`}
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
          chat.active && <ChatWindow key={index} chat={chat} isSingleChat={isSingleChat} />
      ))}
    </div>
  )
}
