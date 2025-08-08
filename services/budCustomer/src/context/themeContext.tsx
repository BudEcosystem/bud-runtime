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

  // Ant Design theme configuration using CSS variables
  const getCSSVarValue = (varName: string) => {
    if (typeof window !== 'undefined') {
      return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    }
    return effectiveTheme === 'dark' ?
      (varName === '--bg-primary' ? '#0A0A0A' : '#965CDE') :
      (varName === '--bg-primary' ? '#FFFFFF' : '#965CDE');
  };

  const antdThemeConfig = {
    algorithm: effectiveTheme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: getCSSVarValue('--color-purple') || '#965CDE',
      colorBgContainer: getCSSVarValue('--bg-primary') || (effectiveTheme === 'dark' ? '#0A0A0A' : '#FFFFFF'),
      colorBgElevated: getCSSVarValue('--bg-card') || (effectiveTheme === 'dark' ? '#161616' : '#FFFFFF'),
      colorBgLayout: getCSSVarValue('--bg-primary') || (effectiveTheme === 'dark' ? '#0A0A0A' : '#F5F5F5'),
      colorText: getCSSVarValue('--text-primary') || (effectiveTheme === 'dark' ? '#EEEEEE' : '#1A1A1A'),
      colorTextSecondary: getCSSVarValue('--text-muted') || (effectiveTheme === 'dark' ? '#B3B3B3' : '#666666'),
      colorTextTertiary: getCSSVarValue('--text-disabled') || (effectiveTheme === 'dark' ? '#757575' : '#999999'),
      colorBorder: getCSSVarValue('--border-color') || (effectiveTheme === 'dark' ? '#1F1F1F' : '#E0E0E0'),
      colorBorderSecondary: getCSSVarValue('--border-secondary') || (effectiveTheme === 'dark' ? '#2F2F2F' : '#D0D0D0'),
      colorFill: getCSSVarValue('--bg-hover') || (effectiveTheme === 'dark' ? '#1F1F1F' : '#F0F0F0'),
      colorFillSecondary: getCSSVarValue('--bg-secondary') || (effectiveTheme === 'dark' ? '#161616' : '#F5F5F5'),
      colorFillTertiary: getCSSVarValue('--bg-tertiary') || (effectiveTheme === 'dark' ? '#0F0F0F' : '#FAFAFA'),
      borderRadius: 8,
      fontSize: 14,
    },
    components: {
      Button: {
        colorPrimaryHover: getCSSVarValue('--color-purple-hover') || '#A76FE8',
        colorPrimaryActive: getCSSVarValue('--color-purple-active') || '#8549D2',
      },
      Table: {
        colorBgContainer: getCSSVarValue('--bg-primary'),
        colorBorderSecondary: getCSSVarValue('--border-color'),
        rowHoverBg: getCSSVarValue('--bg-hover'),
      },
      Modal: {
        contentBg: getCSSVarValue('--bg-modal'),
        headerBg: getCSSVarValue('--bg-modal'),
        footerBg: getCSSVarValue('--bg-modal'),
      },
      Input: {
        colorBgContainer: getCSSVarValue('--bg-tertiary'),
        colorBorder: getCSSVarValue('--border-secondary'),
        colorText: getCSSVarValue('--text-primary'),
        colorTextPlaceholder: getCSSVarValue('--text-disabled'),
      },
      Select: {
        colorBgContainer: getCSSVarValue('--bg-tertiary'),
        colorBorder: getCSSVarValue('--border-secondary'),
        optionSelectedBg: getCSSVarValue('--bg-hover'),
      },
      Tabs: {
        colorBorderSecondary: getCSSVarValue('--border-color'),
        itemActiveColor: getCSSVarValue('--text-primary'),
        itemColor: getCSSVarValue('--text-muted'),
        itemHoverColor: getCSSVarValue('--text-primary'),
      },
      Popover: {
        colorBgElevated: getCSSVarValue('--bg-card'),
        colorText: getCSSVarValue('--text-primary'),
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
