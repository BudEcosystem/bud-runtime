import { createContext } from "react";
import { PostMessage } from "../components/bud/hooks/useMessages";
import { ActiveSession, Session } from "../components/bud/chat/HistoryList";



type Provider = {
  id: string;
  name: string;
  description: string;
  type: string;
  icon: string;
};
type Tag = {
  name: string;
  color: string;
};

type Model = {
  id: string;
  name: string;
  description: string;
  uri: string;
  tags: Tag[];
  provider: Provider;
  is_present_in_model: boolean;
};

type Project = {
  name: string;
  description: string;
  tags: Tag[];
  icon: string;
  id: string;
};

export type Endpoint = {
  id: string;
  name: string;
  status: string;
  model: Model;
  project: Project;
  created_at: string;
};

type ChatContextType = {
  // api key
  chat?: ActiveSession;
  // endpoints
  endpoints: Endpoint[];
  // set endpoints
  setEndpoints: (endpoints: Endpoint[]) => void;
  // messages history
  messages: PostMessage[];
  // set messages history
  setMessages: (messages: PostMessage[]) => void;

};

const ChatContext = createContext<ChatContextType>({
  // default values
  chat: undefined,
  endpoints: [],
  setEndpoints: (_: Endpoint[]) => {},
  messages: [],
  setMessages: (_: any[]) => {},
});

export default ChatContext;
