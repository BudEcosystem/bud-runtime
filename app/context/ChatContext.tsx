import { createContext } from "react";
import { apiKey } from "../components/bud/environment";

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
};

const ChatContext = createContext<ChatContextType>({
  // default values
  apiKey: apiKey || "",
  token: "",
  endpoints: [],
  setEndpoints: (endpoints: Endpoint[]) => {},
  setToken: (token: string) => {},
  setApiKey: (apiKey: string) => {},
});

export default ChatContext;
