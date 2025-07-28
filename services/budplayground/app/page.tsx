"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./context/AuthContext";
import { useLoader } from "./context/LoaderContext";



export default function Home() {

    const { apiKey, isLoading } = useAuth();
    const { showLoader, hideLoader } = useLoader();
    const router = useRouter();



    useEffect(() => {
        if (!apiKey && !isLoading) {
            router.push('/login');
        } else {
            router.push('/chat');
        }
        if(!isLoading){
            hideLoader();
        }
    }, [apiKey, isLoading, hideLoader, router]);

    return <div>
        Welcome to the chat
    </div>;
}
