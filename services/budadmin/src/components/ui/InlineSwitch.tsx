import { Switch } from "antd";
import React from "react";

interface InlineSwitchProps {
  value?: boolean;
  defaultValue: boolean;
  onChange: (value: boolean) => void;
}

export default function InlineSwitch(props: InlineSwitchProps) {
  return (
    <div className="flex flex-row items-center">
      <Switch
        value={props.value}
        defaultValue={props.defaultValue}
        onChange={(e) => props.onChange(e)}
      />
    </div>
  );
}
