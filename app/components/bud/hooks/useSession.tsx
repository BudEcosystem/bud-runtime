import { useContext, useState } from "react";
import { useChat } from "./useChat";

import { Message } from "@ai-sdk/react";
import ChatContext from "@/app/context/ChatContext";
import { ActiveSession } from "../chat/HistoryList";

export type Usage = {
    completionTokens: number;
    promptTokens: number;
    totalTokens: number;
};

export type Metrics = {
    e2e_latency: number;
    throughput: number;
    ttft: number;
    itl: number;
}

export type SavedMessage = {
    deployment_id: string;
    prompt: string;
    usage: Usage;
    message: Message;
    metrics: Metrics;
}

export function useSession(chatId: string) {
    const { chat, setChat } = useContext(ChatContext);
    const [chatHistory, setChatHistory] = useState<SavedMessage[]>([]);
    const { getChat, updateHistory } = useChat();
    // const chat = await getChat(chatId);
    // const { messages, setMessages } = useState<Message[]>([]);
    // loadChatHistory();

    function saveToLocalStorage(message: SavedMessage) {
        const existing = localStorage.getItem(chatId);
        if (existing) {
            const data = JSON.parse(existing);
            data.push(message);
            localStorage.setItem(chatId, JSON.stringify(data));
        } else {
            localStorage.setItem(chatId, JSON.stringify([message]));
        }
    }

    function saveMessage(message: SavedMessage) {
        // const metrics: Metrics | JSONValue | undefined = message.annotations?.find((item: any) => item.type == 'metrics')
        saveToLocalStorage(message);
        const chatSession: ActiveSession = {
            id: chatId,
            name: message.prompt,
            total_tokens: message.usage.totalTokens,
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
        };
        updateHistory(chatSession);
    }

    function loadFromLocalStorage() {
        const chatHistory = localStorage.getItem(chatId);
        let chatHistoryArray: SavedMessage[] = [];
        if (chatHistory) {
            chatHistoryArray = JSON.parse(chatHistory);
        }
        return chatHistoryArray;
    }

    function loadChatHistory() {
        const chatHistory = loadFromLocalStorage();
        console.log('chatHistory', chatHistory);
        setChatHistory(chatHistory);
        return chatHistory;
    }
    return { saveMessage, chatHistory, loadChatHistory };
}
