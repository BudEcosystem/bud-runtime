'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { SettingsType } from '../schema/SettingsSidebar';

interface SettingsContextType {
  isOpen: boolean;
  activeSettings: SettingsType;
  selectedNodeId?: string;
  selectedNodeData?: any;
  openSettings: (nodeType: string, nodeId?: string, nodeData?: any) => void;
  closeSettings: () => void;
  toggleSettings: () => void;
  setActiveSettings: (type: SettingsType) => void;
}

const SettingsContext = createContext<SettingsContextType>({
  isOpen: false,
  activeSettings: SettingsType.INPUT,
  openSettings: () => {},
  closeSettings: () => {},
  toggleSettings: () => {},
  setActiveSettings: () => {},
});

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeSettings, setActiveSettings] = useState<SettingsType>(SettingsType.INPUT);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [selectedNodeData, setSelectedNodeData] = useState<any>();

  const openSettings = useCallback((nodeType: string, nodeId?: string, nodeData?: any) => {
    // Map node types to settings types - check if nodeType or nodeId contains the keyword
    let settingsType: SettingsType;
    const typeToCheck = nodeType.toLowerCase();
    const idToCheck = nodeId?.toLowerCase() || '';

    if (typeToCheck.includes('systemprompt') || idToCheck.includes('systemprompt')) {
      settingsType = SettingsType.SYSTEM_PROMPT;
    } else if (typeToCheck.includes('promptmessages') || idToCheck.includes('promptmessages')) {
      settingsType = SettingsType.PROMPT_MESSAGE;
    } else if (typeToCheck.includes('output') || idToCheck.includes('output')) {
      settingsType = SettingsType.OUTPUT;
    } else if (typeToCheck.includes('multiinputs') || typeToCheck.includes('cardinput') ||
               idToCheck.includes('multiinputs') || idToCheck.includes('cardinput')) {
      settingsType = SettingsType.INPUT;
    } else {
      // Default to input settings for unknown types
      settingsType = SettingsType.INPUT;
    }

    setActiveSettings(settingsType);
    setSelectedNodeId(nodeId);
    setSelectedNodeData(nodeData);
    setIsOpen(true);
  }, []);

  const closeSettings = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggleSettings = useCallback(() => {
    if (isOpen) {
      closeSettings();
    } else {
      setActiveSettings(SettingsType.INPUT);
      setIsOpen(true);
    }
  }, [isOpen, closeSettings]);

  const handleSetActiveSettings = useCallback((type: SettingsType) => {
    setActiveSettings(type);
  }, []);

  return (
    <SettingsContext.Provider
      value={{
        isOpen,
        activeSettings,
        selectedNodeId,
        selectedNodeData,
        openSettings,
        closeSettings,
        toggleSettings,
        setActiveSettings: handleSetActiveSettings,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};
