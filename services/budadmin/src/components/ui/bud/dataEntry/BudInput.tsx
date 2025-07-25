import React from "react";
import { Text_12_400_787B83 } from "../../text";
import { Form, FormRule, Input } from "antd";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  name: string;
  label: string;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  style?: React.CSSProperties;
  compId: string;
  errors?: any;
  rules: FormRule[]
}

function BudInput(props: BudInputProps) {

  return (
    <Form.Item
    hasFeedback
    name={props.name} rules={props.rules}>
      <label className="pb-1 mt-3 block">
        <Text_12_400_787B83 className="pb-1">{props.label}</Text_12_400_787B83>
        <Input
          name={props.name}
          placeholder={props.placeholder}
          disabled={props.disabled}
          className={props.className}
          style={props.style}
        />
      </label>
    </Form.Item>
  );
}

export default BudInput;
