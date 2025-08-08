"use client";

import React, { createContext, useContext, useEffect, useState } from 'react';
import { ConfigProvider, theme as antdTheme } from 'antd';

export type ThemeMode = 'dark' | 'light' | 'system';

interface ThemeContextType {
  theme: ThemeMode;
  effectiveTheme: 'dark' | 'light';
  setTheme: (theme: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeMode>('dark');
  const [effectiveTheme, setEffectiveTheme] = useState<'dark' | 'light'>('dark');

  // Load theme from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as ThemeMode | null;
    if (savedTheme) {
      setThemeState(savedTheme);
    }
  }, []);

  // Determine effective theme based on system preference
  useEffect(() => {
    const updateEffectiveTheme = () => {
      if (theme === 'system') {
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        setEffectiveTheme(systemTheme);
      } else {
        setEffectiveTheme(theme as 'dark' | 'light');
      }
    };

    updateEffectiveTheme();

    // Listen for system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => updateEffectiveTheme();

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      mediaQuery.addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleChange);
      } else {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, [theme]);

  // Update document class and localStorage
  useEffect(() => {
    document.documentElement.classList.remove('dark', 'light');
    document.documentElement.classList.add(effectiveTheme);
    document.documentElement.setAttribute('data-theme', effectiveTheme);
  }, [effectiveTheme]);

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  // Ant Design theme configuration
  const antdThemeConfig = {
    algorithm: effectiveTheme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: '#965CDE',
      colorBgContainer: effectiveTheme === 'dark' ? '#0A0A0A' : '#FFFFFF',
      colorBgElevated: effectiveTheme === 'dark' ? '#161616' : '#FFFFFF',
      colorBgLayout: effectiveTheme === 'dark' ? '#0A0A0A' : '#F5F5F5',
      colorText: effectiveTheme === 'dark' ? '#EEEEEE' : '#1A1A1A',
      colorTextSecondary: effectiveTheme === 'dark' ? '#B3B3B3' : '#666666',
      colorTextTertiary: effectiveTheme === 'dark' ? '#757575' : '#999999',
      colorBorder: effectiveTheme === 'dark' ? '#1F1F1F' : '#E0E0E0',
      colorBorderSecondary: effectiveTheme === 'dark' ? '#2F2F2F' : '#D0D0D0',
      colorFill: effectiveTheme === 'dark' ? '#1F1F1F' : '#F0F0F0',
      colorFillSecondary: effectiveTheme === 'dark' ? '#161616' : '#F5F5F5',
      colorFillTertiary: effectiveTheme === 'dark' ? '#0F0F0F' : '#FAFAFA',
      borderRadius: 8,
      fontSize: 14,
    },
    components: {
      Button: {
        colorPrimaryHover: '#A76FE8',
        colorPrimaryActive: '#8549D2',
      },
      Table: {
        colorBgContainer: effectiveTheme === 'dark' ? '#0A0A0A' : '#FFFFFF',
        colorBorderSecondary: effectiveTheme === 'dark' ? '#1F1F1F' : '#E0E0E0',
        rowHoverBg: effectiveTheme === 'dark' ? '#161616' : '#F5F5F5',
      },
      Modal: {
        contentBg: effectiveTheme === 'dark' ? '#161616' : '#FFFFFF',
        headerBg: effectiveTheme === 'dark' ? '#161616' : '#FFFFFF',
        footerBg: effectiveTheme === 'dark' ? '#161616' : '#FFFFFF',
      },
      Input: {
        colorBgContainer: effectiveTheme === 'dark' ? '#1F1F1F' : '#FFFFFF',
        colorBorder: effectiveTheme === 'dark' ? '#2F2F2F' : '#D0D0D0',
        colorText: effectiveTheme === 'dark' ? '#EEEEEE' : '#1A1A1A',
        colorTextPlaceholder: effectiveTheme === 'dark' ? '#757575' : '#999999',
      },
      Select: {
        colorBgContainer: effectiveTheme === 'dark' ? '#1F1F1F' : '#FFFFFF',
        colorBorder: effectiveTheme === 'dark' ? '#2F2F2F' : '#D0D0D0',
        optionSelectedBg: effectiveTheme === 'dark' ? '#2F2F2F' : '#F0F0F0',
      },
      Tabs: {
        colorBorderSecondary: effectiveTheme === 'dark' ? '#1F1F1F' : '#E0E0E0',
        itemActiveColor: effectiveTheme === 'dark' ? '#EEEEEE' : '#1A1A1A',
        itemColor: effectiveTheme === 'dark' ? '#B3B3B3' : '#666666',
        itemHoverColor: effectiveTheme === 'dark' ? '#EEEEEE' : '#1A1A1A',
      },
      Popover: {
        colorBgElevated: effectiveTheme === 'dark' ? '#161616' : '#FFFFFF',
        colorText: effectiveTheme === 'dark' ? '#EEEEEE' : '#1A1A1A',
      },
    },
  };

  return (
    <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme }}>
      <ConfigProvider theme={antdThemeConfig}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
};
