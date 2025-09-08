"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

interface OverlayContextType {
  isVisible: boolean;
  setOverlayVisible: (isVisible: boolean) => void;
}

const OverlayContext = createContext<OverlayContextType | undefined>(undefined);

export const useOverlay = (): OverlayContextType => {
  const context = useContext(OverlayContext);
  if (!context) {
    throw new Error("useOverlay must be used within an OverlayProvider");
  }
  return context;
};

interface OverlayProviderProps {
  children: ReactNode;
}

export const OverlayProvider: React.FC<OverlayProviderProps> = ({
  children,
}) => {
  const [isVisible, setIsVisible] = useState(false);

  const setOverlayVisible = (visible: boolean) => {
    setIsVisible(visible);
  };

  const value: OverlayContextType = {
    isVisible,
    setOverlayVisible,
  };

  return (
    <OverlayContext.Provider value={value}>{children}</OverlayContext.Provider>
  );
};
