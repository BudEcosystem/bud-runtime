import { Switch } from "antd";
import React from "react";

interface InlineSwitchProps {
  title: string;
  value: boolean;
  defaultValue: boolean;
  onChange: (value: boolean) => void;
}

export default function InlineSwitch(props: InlineSwitchProps) {
  return (
    <div className="flex flex-row items-center gap-[.625rem] p-[.5rem]">
      <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
        {props.title}
      </span>
      <Switch
        defaultChecked={props.defaultValue}
        checked={props.value}
        onChange={(e) => props.onChange(e)}
      />
    </div>
  );
}
