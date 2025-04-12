import { v4 as uuidv4 } from 'uuid';

import { useContext, useMemo, useState } from "react";
import RootContext from "@/app/context/RootContext";
import { ActiveSession } from "../chat/HistoryList";
import ChatContext, { Endpoint } from '@/app/context/ChatContext';

export function useChat() {
    const { chats, setChats, activeChatList, setActiveChatList } = useContext(RootContext);
    const { chat, setChat } = useContext(ChatContext);

    
    function saveHistoryToLocalStorage(chatHistory: ActiveSession[]) {
        localStorage.setItem("chatHistory", JSON.stringify(chatHistory));
    }
    
    function saveHistory(chatHistory: ActiveSession[]) {
        saveHistoryToLocalStorage(chatHistory);
        setChats(chatHistory);
    }


    function loadHistoryFromLocalStorage() {
        const chatHistory = localStorage.getItem("chatHistory");
        if (chatHistory) {
            return JSON.parse(chatHistory);
        }
        return [];
    }

    function loadHistory() {
        const history = loadHistoryFromLocalStorage();
        setChats(history);
        const activeList = history.filter((item: ActiveSession) => item.active);
        setActiveChatList(activeList);
        console.log("activeList", activeList);
        if (activeList.length === 0) {
            createChat();
        }
        return history;
    }

    function updateHistory(chatSession: ActiveSession) {
        const updatedHistory = [...chats];
        const existing = updatedHistory.find((item: ActiveSession) => item.id === chatSession.id);
        console.log("existing", chatSession);
        if (existing) {
            existing.name = existing.name === "New Chat" ? chatSession.name : existing.name;
            existing.total_tokens = chatSession.total_tokens;
        } else {
            updatedHistory.push(chatSession);
        }
        saveHistory(updatedHistory);
    }

    function deactivateChat(chatId: string) {
        console.log("deactivateChat", chatId);
        const chatList = loadHistory();
        console.log("chatList", chatList);
        const updatedChatList = chatList.map((item: ActiveSession) => {
            if (item.id === chatId) {
                item.active = false;
            }
            return item;
        });
        console.log("updatedChatList", updatedChatList);
        saveHistory(updatedChatList);
        setChats(updatedChatList);

        setActiveChatList(updatedChatList.filter((item: ActiveSession) => item.active));
    }

    async function createChat() {
        

        const newChatPayload = {
            id: uuidv4(),
            name: `New Chat`,
            chat_setting_id: "default",
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
            total_tokens: 0,
            active: true,
        };

        const updatedChats = [...chats];
        updatedChats.push(newChatPayload);
        setChats(updatedChats);
        saveHistory(updatedChats);
        setActiveChatList(updatedChats.filter((item: ActiveSession) => item.active));
    }

    async function closeChat(chatId: string) {
        deactivateChat(chatId);
    }

    async function getChat(chatId: string) {
        return chats.find((chat: any) => chat.id === chatId);
    }

    function setDeployment(chatId: string, endpoint: Endpoint) {
        const updatedChat = { ...chat } as ActiveSession;
        updatedChat.selectedDeployment = endpoint;
        setChat(updatedChat);
        
        const filteredChat = chats.find((chat: any) => chat.id === chatId);
        if (filteredChat) {
            filteredChat.selectedDeployment = endpoint;
            setChats(chats);
            saveHistory(chats);
            setActiveChatList(chats.filter((chat: ActiveSession) => chat.active));
        }
    }

    return { createChat, closeChat, getChat, setDeployment, loadHistory, updateHistory, activeChatList };
}
