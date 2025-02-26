import { createContext } from "react";

type RootContextType = {
  chats: any[];
  setChats: (chats: any[]) => void;
  createChat: () => void;
};

const RootContext = createContext<RootContextType>({
  chats: [],
  setChats: () => {},
  createChat: () => {},
});

export default RootContext;
