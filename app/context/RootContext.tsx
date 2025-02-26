import { createContext } from "react";
import { ChatType } from "../page";

type RootContextType = {
  chats: ChatType[];
  setChats: (chats: any[]) => void;
  createChat: () => void;
};

const RootContext = createContext<RootContextType>({
  chats: [],
  setChats: () => {},
  createChat: () => {},
});

export default RootContext;
