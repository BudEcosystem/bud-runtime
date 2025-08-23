import React from "react";
import { Input } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";

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
      prefix={<Icon icon="material-symbols:search" className="text-[var(--text-muted)]" />}
      className={`bg-[var(--bg-tertiary)] border-[var(--border-secondary)] text-[var(--text-primary)] ${className}`}
      style={{
        backgroundColor: "var(--bg-tertiary)",
        borderColor: "var(--border-secondary)",
        color: "var(--text-primary)",
      }}
    />
  );
};

export default SearchHeaderInput;
