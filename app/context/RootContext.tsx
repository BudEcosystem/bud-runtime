"use client";

import { ChangeEvent, createContext, FormEvent, ReactNode, useState } from "react";
import { ActiveSession } from "../components/bud/chat/HistoryList";
import { Endpoint } from "./ChatContext";
import { SavedMessage } from "../components/bud/hooks/useSession";

type RootContextType = {
  chats: ActiveSession[];
  setChats: (chats: ActiveSession[]) => void;
  activeChatList: ActiveSession[];
  setActiveChatList: (activeChatList: ActiveSession[]) => void;
  endpoints: Endpoint[];
  setEndpoints: (endpoints: Endpoint[]) => void;
  sharedChatInput: ChangeEvent<HTMLInputElement>;
  setSharedChatInput: (input: ChangeEvent<HTMLInputElement>) => void;
  submitInput: FormEvent<Element>;
  setSubmitInput: (input: FormEvent<Element>) => void;
};

const RootContext = createContext<RootContextType>({
  chats: [],
  setChats: () => {},
  activeChatList: [],
  setActiveChatList: () => {},
  endpoints: [],
  setEndpoints: (_: Endpoint[]) => {},
  sharedChatInput: {} as ChangeEvent<HTMLInputElement>,
  setSharedChatInput: (_: ChangeEvent<HTMLInputElement>) => {},
  submitInput: {} as FormEvent<Element>,
  setSubmitInput: (_: FormEvent<Element>) => {},
});

export const RootProvider = ({ children }: { children: ReactNode }) => {
  const [chats, setChats] = useState<ActiveSession[]>([]);
  const [sharedChatInput, setSharedChatInput] = useState<ChangeEvent<HTMLInputElement>>({} as ChangeEvent<HTMLInputElement>);
  const [submitInput, setSubmitInput] = useState<FormEvent<Element>>({} as FormEvent<Element>);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [activeChatList, setActiveChatList] = useState<ActiveSession[]>([]);
  return <RootContext.Provider value={{ 
    chats, setChats, sharedChatInput, setSharedChatInput, submitInput, setSubmitInput,
    endpoints, setEndpoints, activeChatList, setActiveChatList
  }}>{children}</RootContext.Provider>;
};

export default RootContext;