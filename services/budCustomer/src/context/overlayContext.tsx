import React, { createContext, useContext, useState, ReactNode } from 'react';

interface OverlayContextType {
  isOverlayVisible: boolean;
  showOverlay: () => void;
  hideOverlay: () => void;
  toggleOverlay: () => void;
}

const OverlayContext = createContext<OverlayContextType | undefined>(undefined);

export const useOverlay = (): OverlayContextType => {
  const context = useContext(OverlayContext);
  if (!context) {
    throw new Error('useOverlay must be used within an OverlayProvider');
  }
  return context;
};

interface OverlayProviderProps {
  children: ReactNode;
}

export const OverlayProvider: React.FC<OverlayProviderProps> = ({ children }) => {
  const [isOverlayVisible, setIsOverlayVisible] = useState(false);

  const showOverlay = () => setIsOverlayVisible(true);
  const hideOverlay = () => setIsOverlayVisible(false);
  const toggleOverlay = () => setIsOverlayVisible(prev => !prev);

  const value: OverlayContextType = {
    isOverlayVisible,
    showOverlay,
    hideOverlay,
    toggleOverlay,
  };

  return (
    <OverlayContext.Provider value={value}>
      {children}
    </OverlayContext.Provider>
  );
};