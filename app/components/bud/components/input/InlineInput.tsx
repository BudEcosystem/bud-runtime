import { Input } from "antd";
import React from "react";

interface InlineInputProps {
  title: string;
  value: string;
  defaultValue: string;
  type: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

export default function InlineInput(props: InlineInputProps) {
  return (
    <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
      <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
        {props.title}
      </span>
      <div className="flex flex-row items-center gap-[.5rem]">
        <Input
          type={props.type}
          placeholder={props.placeholder}
          value={props.value}
          defaultValue={props.defaultValue}
          onChange={(e) => props.onChange(e.target.value)}
          className="bg-[#101010] text-[#EEEEEE] border-[1px] border-[#1F1F1F] rounded-[0.5rem] p-[.5rem] w-full"
        />
      </div>
    </div>
  );
}
