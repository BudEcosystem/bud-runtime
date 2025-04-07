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
  strengths: string[];
  limitations: string[];
  icon: string;
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
  status: "unhealthy" | "running";
  model: Model;
  project: Project;
  created_at: string;
};

export type Note = {
  id: string;
  note: string;
  created_at: string;
  modified_at: string;
};

type ChatContextType = {
  // api key
  chat?: ActiveSession;

  // messages history
  messages: PostMessage[];
  // set messages history
  setMessages: (messages: PostMessage[]) => void;

  notes: Note[];
  setNotes: (notes: Note[]) => void;
};

const ChatContext = createContext<ChatContextType>({
  // default values
  chat: undefined,
  messages: [],
  setMessages: (_: any[]) => {},
  notes: [],
  setNotes: (_: Note[]) => {},
});

export default ChatContext;
