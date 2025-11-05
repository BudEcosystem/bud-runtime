import React, { createContext, useContext, useState, ReactNode } from 'react';

interface ModelSettingsContextType {
  isOpen: boolean;
  openModelSettings: () => void;
  closeModelSettings: () => void;
  toggleModelSettings: () => void;
}

const ModelSettingsContext = createContext<ModelSettingsContextType | undefined>(undefined);

export const ModelSettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);

  const openModelSettings = () => {
    setIsOpen(true);
  };

  const closeModelSettings = () => {
    setIsOpen(false);
  };

  const toggleModelSettings = () => {
    setIsOpen(prev => !prev);
  };

  return (
    <ModelSettingsContext.Provider
      value={{
        isOpen,
        openModelSettings,
        closeModelSettings,
        toggleModelSettings,
      }}
    >
      {children}
    </ModelSettingsContext.Provider>
  );
};

export const useModelSettings = () => {
  const context = useContext(ModelSettingsContext);
  if (context === undefined) {
    throw new Error('useModelSettings must be used within a ModelSettingsProvider');
  }
  return context;
};
