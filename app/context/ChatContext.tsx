import { createContext } from "react";
import { apiKey } from "../components/bud/environment";
import { PostMessage } from "../components/bud/hooks/useMessages";

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
  apiKey: string;
  // token
  token: string;
  // endpoints
  endpoints: Endpoint[];
  // set endpoints
  setEndpoints: (endpoints: Endpoint[]) => void;
  // set token
  setToken: (token: string) => void;
  // set api key
  setApiKey: (apiKey: string) => void;
  // chat session id
  chatSessionId: string;
  // set chat session id
  setChatSessionId: (chatSessionId: string) => void;
  // messages history
  messages: PostMessage[];
  // set messages history
  setMessages: (messages: PostMessage[]) => void;
};

const ChatContext = createContext<ChatContextType>({
  // default values
  apiKey: apiKey || "",
  token: "",
  endpoints: [],
  setEndpoints: (endpoints: Endpoint[]) => {},
  setToken: (token: string) => {},
  setApiKey: (apiKey: string) => {},
  chatSessionId: "",
  setChatSessionId: (chatSessionId: string) => {},
  messages: [],
  setMessages: (messages: any[]) => {},
});

export default ChatContext;
