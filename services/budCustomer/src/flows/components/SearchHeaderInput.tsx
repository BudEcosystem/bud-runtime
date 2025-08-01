import React from 'react';
import { Input } from 'antd';
import { Icon } from '@iconify/react/dist/iconify.js';

interface SearchHeaderInputProps {
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  onSearch?: (value: string) => void;
  className?: string;
}

const SearchHeaderInput: React.FC<SearchHeaderInputProps> = ({
  placeholder = "Search...",
  value,
  onChange,
  onSearch,
  className = "",
}) => {
  return (
    <Input
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      onPressEnter={(e) => onSearch?.((e.target as HTMLInputElement).value)}
      prefix={<Icon icon="material-symbols:search" className="text-gray-400" />}
      className={`bg-[#1A1A1A] border-[#2A2A2A] text-white ${className}`}
      style={{
        backgroundColor: '#1A1A1A',
        borderColor: '#2A2A2A',
        color: 'white',
      }}
    />
  );
};

export default SearchHeaderInput;
