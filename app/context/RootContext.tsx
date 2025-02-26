import { createContext } from "react";
import { ChatType } from "../page";
import { Endpoint } from "./ChatContext";

type RootContextType = {
  chats: ChatType[];
  setChats: (chats: any[]) => void;
  createChat: () => void;
  handleDeploymentSelect: (chat: ChatType, endpoint: Endpoint) => void;
  handleSettingsChange: (chat: ChatType, prop: string, value: any) => void;
};

const RootContext = createContext<RootContextType>({
  chats: [],
  setChats: () => {},
  createChat: () => {},
  handleDeploymentSelect: (chat: ChatType, endpoint: Endpoint) => {},
  handleSettingsChange: (chat: ChatType, prop: string, value: any) => {},
});

export default RootContext;
