"use client";

import { useEffect, useState, useCallback } from "react";
import { v4 as uuidv4 } from 'uuid';
import { useLoader } from "../context/LoaderContext";
import { useRouter } from 'next/navigation';

import { useChatStore } from "../store/chat";
import { Session } from "../types/chat";
import ChatWindow from "./components/ChatWindow";
import { useAuth } from "../context/AuthContext";
import { Endpoint } from "../types/deployment";
import { tempApiBaseUrl } from "../lib/environment";

export default function ChatPage() {
  const { activeChatList, createChat, setPromptIds, getPromptIds, setActiveChatList, clearPromptSessions, clearDefaultSessions, hasPromptSessions } = useChatStore();
  const { hideLoader } = useLoader();
  const { apiKey, isLoading, isSessionValid } = useAuth();
  const router = useRouter();

  const [hasHydrated, setHasHydrated] = useState(false);
  const [isSingleChat, setIsSingleChat] = useState(false);
  const [selectedModel, setSelectedModel] = useState("");
  const [promptIdsFromUrl, setPromptIdsFromUrl] = useState<string[]>([]);

  const createNewChat = useCallback(() => {
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

  }, [selectedModel, createChat]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      // Store is now always hydrated since we use custom persistence
      setHasHydrated(true);
    }
  }, []);


  // Create chat sessions based on promptIds or default
  useEffect(() => {
    if (!hasHydrated) return;

    hideLoader();

    // PROMPT MODE: Has promptIds in URL
    if (promptIdsFromUrl.length > 0) {
      console.log('[Session] Prompt mode - promptIds:', promptIdsFromUrl);

      // Check if existing chats match the promptIds (same IDs in same order)
      const existingChatIds = activeChatList.map(chat => chat.id);
      const promptIdsMatch = promptIdsFromUrl.length === existingChatIds.length &&
        promptIdsFromUrl.every((id, index) => existingChatIds[index] === id);

      if (!promptIdsMatch) {
        console.log('[Session] Creating new prompt sessions');

        // Clear any default sessions first (isolate modes)
        clearDefaultSessions();

        // Create new chats from promptIds
        const newChats: Session[] = promptIdsFromUrl.map((promptId, index) => {
          const newChatPayload: Session = {
            id: promptId,
            name: `Prompt ${index + 1}`,
            chat_setting_id: "default",
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
            total_tokens: 0,
            active: true,
          };

          if (selectedModel) {
            const selectedDeployment: Endpoint = {
              name: selectedModel,
              id: "default",
              status: "running",
              model: "default",
              project: null,
              created_at: new Date().toISOString()
            };
            newChatPayload.selectedDeployment = selectedDeployment;
          }

          return newChatPayload;
        });

        // Set all chats at once
        setActiveChatList(newChats);
      } else {
        console.log('[Session] Prompt sessions already match URL');
      }
    }
    // DEFAULT MODE: No promptIds in URL
    else {
      console.log('[Session] Default mode');

      // Clear any prompt sessions to isolate modes
      if (hasPromptSessions()) {
        console.log('[Session] Clearing prompt sessions for default mode');
        clearPromptSessions();
      }

      // Check if we have any default sessions left
      const defaultSessions = activeChatList.filter(chat => !chat.id.startsWith('prompt_'));

      if (defaultSessions.length === 0) {
        console.log('[Session] Creating new default session');
        createNewChat();
      }
    }
  }, [hasHydrated, promptIdsFromUrl, selectedModel, activeChatList, createNewChat, hideLoader, setActiveChatList, clearPromptSessions, clearDefaultSessions, hasPromptSessions]);

  // Handle URL parameters for page configuration (not authentication)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const isSingleChat = params.get('is_single_chat');
    const model = params.get('model');
    const promptIds = params.get('promptIds');

    if(isSingleChat == "true") {
      setIsSingleChat(true);
    }
    if(model) {
      setSelectedModel(model);
    }
    if(promptIds) {
      // Parse comma-separated promptIds
      const idsArray = promptIds.split(',').map(id => id.trim()).filter(id => id.length > 0);
      if(idsArray.length > 0) {
        setPromptIdsFromUrl(idsArray);
        setPromptIds(idsArray);
      }
      console.log('Extracted promptIds from URL:', idsArray);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle authentication state changes
  useEffect(() => {
    if (isLoading) {
      return; // Wait for auth to finish loading
    }

    // ============================================================================
    // TODO: TEMPORARY - AUTHENTICATION DISABLED FOR LOCAL DEVELOPMENT
    // ============================================================================
    // To re-enable authentication, uncomment the lines below:
    //
    if (!apiKey && !isSessionValid) {
      // No authentication, redirect to login
      router.replace('/login');
    } else {
      // Authentication successful, hide loader
      hideLoader();
    }
    // ============================================================================

    // TEMPORARY: Always hide loader (skip auth check)
    hideLoader();

  }, [apiKey, isSessionValid, isLoading, router, hideLoader]);

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
