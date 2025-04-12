"use client";

import { useRouter } from "next/navigation";
import { useCallback, useContext, useEffect, useMemo } from "react";
import { useAuth } from "./context/AuthContext";
import { useLoader } from "./context/LoaderContext";
import RootContext, { RootProvider } from "./context/RootContext";
import Chat from "./components/Chat";
import { ActiveSession } from "./components/bud/chat/HistoryList";
import { useChat } from "./components/bud/hooks/useChat";



export default function Home() {
    const {setChats, chats} = useContext(RootContext);
    
    const { loadHistory } = useChat();
    const { apiKey, isLoading } = useAuth();
    const { showLoader, hideLoader } = useLoader();
    const router = useRouter();

    

    useEffect(() => {
        console.log(apiKey);
        if (!apiKey && !isLoading) {
            router.push('/login');
        }
        if(!isLoading){
            hideLoader();
            loadHistory();
        }
    }, [apiKey, isLoading]);

    return <div>
        <Chat />
    </div>;
}
