import { createContext } from "react";
import { apiKey } from "../components/bud/environment";
import { PostMessage } from "../components/bud/hooks/useMessages";
import { ChatType } from "../page";



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
  chat?: ChatType;
  // token
  token: string;
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
  token: "",
  endpoints: [],
  setEndpoints: (endpoints: Endpoint[]) => {},
  messages: [],
  setMessages: (messages: any[]) => {},
});

export default ChatContext;
