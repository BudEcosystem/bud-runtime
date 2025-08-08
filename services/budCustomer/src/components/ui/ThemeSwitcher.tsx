"use client";

import React from 'react';
import { Dropdown, Button } from 'antd';
import { Icon } from '@iconify/react';
import { useTheme, ThemeMode } from '@/context/themeContext';

const ThemeSwitcher: React.FC = () => {
  const { theme, effectiveTheme, setTheme } = useTheme();

  const themeOptions = [
    {
      key: 'light',
      label: 'Light',
      icon: 'ph:sun',
    },
    {
      key: 'dark',
      label: 'Dark',
      icon: 'ph:moon',
    },
    {
      key: 'system',
      label: 'System',
      icon: 'ph:desktop',
    },
  ];

  const currentIcon = theme === 'system'
    ? 'ph:desktop'
    : theme === 'light'
    ? 'ph:sun'
    : 'ph:moon';

  const items = themeOptions.map((option) => ({
    key: option.key,
    label: (
      <div className="flex items-center gap-2 py-1">
        <Icon
          icon={option.icon}
          className={`w-4 h-4 ${theme === option.key ? 'text-bud-purple' : 'text-bud-text-muted'}`}
        />
        <span className={theme === option.key ? 'text-bud-purple font-medium' : 'text-bud-text-primary'}>
          {option.label}
        </span>
        {theme === option.key && (
          <Icon icon="ph:check" className="w-4 h-4 ml-auto text-bud-purple" />
        )}
      </div>
    ),
    onClick: () => setTheme(option.key as ThemeMode),
  }));

  return (
    <Dropdown
      menu={{ items }}
      placement="bottomRight"
      trigger={['click']}
    >
      <Button
        type="text"
        className="flex items-center justify-center w-10 h-10 rounded-lg hover:bg-bud-bg-hover transition-colors"
        icon={
          <Icon
            icon={currentIcon}
            className="w-5 h-5 text-bud-text-muted"
          />
        }
      />
    </Dropdown>
  );
};

export default ThemeSwitcher;
