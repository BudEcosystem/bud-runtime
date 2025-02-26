import { createContext } from "react";

type RootContextType = {
  // The user's name
  name: string;
  // The user's age
  email: string;
  // api key
  apiKey: string;
  // token
  token: string;
};

const RootContext = createContext<RootContextType>({
  name: "",
  email: "",
  apiKey: "",
  token: "",
});

export default RootContext;
