import { createContext } from "react";
import { Endpoint } from "./ChatContext";
import { ActiveSession, Session } from "../components/bud/chat/HistoryList";

type RootContextType = {
  chats: ActiveSession[];
  setChats: (chats: Session[]) => void;
  createChat: () => void;
  handleDeploymentSelect: (chat: ActiveSession, endpoint: Endpoint) => void;
  handleSettingsChange: (chat: ActiveSession, prop: string, value: any) => void;
  token: string;
  sessions: Session[];
  setSessions: (sessions: Session[]) => void;
};

const RootContext = createContext<RootContextType>({
  chats: [],
  setChats: () => {},
  createChat: () => {},
  handleDeploymentSelect: (chat: ActiveSession, endpoint: Endpoint) => {},
  handleSettingsChange: (chat: ActiveSession, prop: string, value: any) => {},
  token: "",
  sessions: [],
  setSessions: (_: Session[]) => {},
});

export default RootContext;
