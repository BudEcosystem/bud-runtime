// context/OverlayContext.tsx
import { createContext, useContext, useState, ReactNode } from "react";

interface OverlayContextType {
  isVisible: boolean;
  setOverlayVisible: (isVisible: boolean) => void;
}

const OverlayContext = createContext<OverlayContextType | undefined>(undefined);

export const useOverlay = () => {
  const context = useContext(OverlayContext);
  if (!context) {
    throw new Error("useOverlay must be used within an OverlayProvider");
  }
  return context;
};

export const OverlayProvider = ({ children }: { children: ReactNode }) => {
  const [isVisible, setIsVisible] = useState(false);

  const setOverlayVisible = (isVisible: boolean) => {
    setIsVisible(isVisible);
  };

  return (
    <OverlayContext.Provider value={{ isVisible, setOverlayVisible }}>
      {children}
    </OverlayContext.Provider>
  );
};
