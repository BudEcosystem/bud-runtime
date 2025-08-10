import React, {
  createContext,
  Dispatch,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import DynamicFormDrawer from "../../components/ui/bud/drawer/BudDrawer";
import { Form } from "antd";

interface LoaderContextType {
  isLoading: boolean;
  showLoader: () => void;
  hideLoader: () => void;
}

interface AuthNavigationContextType {
  activePage: number;
  setActivePage: Dispatch<React.SetStateAction<number>>;
  authError: string;
  setAuthError: Dispatch<React.SetStateAction<string>>;
}

const LoaderContext = createContext<LoaderContextType | undefined>(undefined);
const AuthNavigationContext = createContext<
  AuthNavigationContextType | undefined
>(undefined);

export const useLoader = () => {
  const context = useContext(LoaderContext);
  if (!context) {
    throw new Error("useLoader must be used within a LoaderProvider");
  }
  return context;
};

export const useAuthNavigation = () => {
  const context = useContext(AuthNavigationContext);
  if (!context) {
    throw new Error(
      "useAuthNavigation must be used within an AuthNavigationProvider",
    );
  }
  return context;
};

export const LoaderProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const showLoader = useCallback(() => setIsLoading(true), []);
  const hideLoader = useCallback(() => setIsLoading(false), []);

  return (
    <LoaderContext.Provider value={{ isLoading, showLoader, hideLoader }}>
      {children}
    </LoaderContext.Provider>
  );
};

export const AuthNavigationProvider: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const [activePage, setActivePage] = useState(1);
  const [authError, setAuthError] = useState("");
  return (
    <AuthNavigationContext.Provider
      value={{ activePage, setActivePage, authError, setAuthError }}
    >
      {children}
    </AuthNavigationContext.Provider>
  );
};

export default { LoaderProvider, AuthNavigationProvider };
