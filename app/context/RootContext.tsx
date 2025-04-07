import { ChangeEvent, createContext, FormEvent } from "react";
import { Endpoint } from "./ChatContext";
import { ActiveSession, Session } from "../components/bud/chat/HistoryList";

type RootContextType = {
  chats: ActiveSession[];
  setChats: (chats: ActiveSession[]) => void;
  createChat: (sessionId?: string, replaceChatId?: string) => void;
  closeChat: (chat: ActiveSession) => void;
  handleDeploymentSelect: (chat: ActiveSession, endpoint: Endpoint) => void;
  handleSettingsChange: (chat: ActiveSession, prop: string, value: any) => void;
  token: string;
  sessions: Session[];
  setSessions: (sessions: Session[]) => void;
  // endpoints
  endpoints: Endpoint[];
  // set endpoints
  setEndpoints: (endpoints: Endpoint[]) => void;
  localMode: boolean;
  // Add a shared input field for synced input across chats
  sharedChatInput: ChangeEvent<HTMLInputElement>;
  setSharedChatInput: (input: ChangeEvent<HTMLInputElement>) => void;
  submitInput: FormEvent<Element>;
  setSubmitInput: (input: FormEvent<Element>) => void;
};

const RootContext = createContext<RootContextType>({
  localMode: false,
  chats: [],
  setChats: () => {},
  createChat: (sessionId?: string, replaceChatId?: string) =>
    console.error("createChat not implemented", sessionId, replaceChatId),
  closeChat: (chat: ActiveSession) =>
    console.error("closeChat not implemented", chat),
  handleDeploymentSelect: (chat: ActiveSession, endpoint: Endpoint) => {},
  handleSettingsChange: (chat: ActiveSession, prop: string, value: any) => {},
  token: "",
  sessions: [],
  setSessions: (_: Session[]) => {},
  endpoints: [],
  setEndpoints: (_: Endpoint[]) => {},
  sharedChatInput: {} as ChangeEvent<HTMLInputElement>,
  setSharedChatInput: (_: ChangeEvent<HTMLInputElement>) => {},
  submitInput: {} as FormEvent<Element>,
  setSubmitInput: (_: FormEvent<Element>) => {},
});

export default RootContext;
