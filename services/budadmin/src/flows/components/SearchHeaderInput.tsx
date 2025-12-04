// SearchHeaderInput.tsx
import { Input } from "antd";
import React, { useRef, useEffect } from "react";

interface SearchHeaderInputProps {
  searchValue: string;
  setSearchValue: (value: string) => void;
  expanded?: boolean;
  placeholder?: string;
  classNames?: string;
  initialWidth?: string;
  iconWidth?: string;
  iconHeight?: string;
  fullWidth?: boolean
}

export default function SearchHeaderInput({
  searchValue,
  setSearchValue,
  expanded = false,
  placeholder = "Search...",
  classNames,
  initialWidth,
  iconWidth = "0.93375rem",
  // iconWidth = '.875rem',
  iconHeight = "0.93375rem",
  // iconHeight = '.885rem',
  fullWidth = false
}: SearchHeaderInputProps) {
  const inputRef = useRef<any>(null);
  const [isExpanded, setIsExpanded] = React.useState(expanded);
  const isMounted = useRef(false);

  // Keep focus when value changes
  useEffect(() => {
    if (isMounted.current && inputRef.current) {
      inputRef.current.focus();
    } else {
      isMounted.current = true;
    }
  }, [searchValue]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchValue(value);
  };

  const handleFocus = () => {
    setIsExpanded(true);
  };

  const handleBlur = () => {
    if (searchValue === "") {
      setIsExpanded(expanded);
    }
  };

  const searchIcon = (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={iconWidth}
      height={iconHeight}
      viewBox="0 0 14 15"
      fill="none"
      className="transition-colors duration-200 text-[#B3B3B3] group-hover:text-white"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M10.5928 6.17143C10.5928 8.74196 8.48067 10.8479 5.84776 10.8479C3.21486 10.8479 1.10273 8.74196 1.10273 6.17143C1.10273 3.6009 3.21486 1.49494 5.84776 1.49494C8.48067 1.49494 10.5928 3.6009 10.5928 6.17143ZM9.48133 10.6997C8.48351 11.4828 7.22091 11.9505 5.84776 11.9505C2.6182 11.9505 0.00012207 9.36313 0.00012207 6.17143C0.00012207 2.97972 2.6182 0.392334 5.84776 0.392334C9.07733 0.392334 11.6954 2.97972 11.6954 6.17143C11.6954 7.61129 11.1626 8.92816 10.2812 9.93997L13.8361 13.451C14.0527 13.665 14.0549 14.014 13.841 14.2307C13.627 14.4473 13.2779 14.4495 13.0613 14.2355L9.48133 10.6997Z"
        fill="currentColor"
      />
    </svg>
  );

  return (
    <Input
      ref={inputRef}
      className={`group custom-ant-input outline-none bg-transparent text-[#EEEEEE] rounded-[6px] pl-[.75rem] py-[0.2625rem] text-[.75rem] font-[400] !placeholder:text-[#757575] cursor-pointer ${classNames}`}
      placeholder={placeholder}
      value={searchValue}
      allowClear
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onKeyDown={(e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
        }
      }}
      style={{
        width: isExpanded ? (expanded ? "100%" : fullWidth? '' : "19.8125rem") : "1.7rem",
        borderColor: isExpanded ? "#757575" : "transparent",
        backgroundColor: isExpanded ? "#1f1f1f" : "transparent",
        transition: "width 0.2s ease-in-out",
      }}
      variant="filled"
      prefix={searchIcon}
      size="large"
      suffix={<div className="w-[0px]"></div>}
    />
  );
}
