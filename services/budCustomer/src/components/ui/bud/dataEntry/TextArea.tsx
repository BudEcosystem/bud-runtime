import React from "react";
import FloatLabel from "./FloatLabel";
import { Form, FormRule, Input } from "antd";
import InfoLabel from "./InfoLabel";
const { TextArea } = Input;

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  name: string;
  label: string;
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  formItemClassnames?: string;
  style?: React.CSSProperties;
  rules: FormRule[];
  info: string;
  required?: boolean;
}

function TextAreaInput(props: BudInputProps) {
  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      // help={false}
      className={`${props.formItemClassnames}`}
      hasFeedback
    >
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text={props.label}
              content={props.info}
              required={props.required}
            />
          }
        >
          <TextArea
            name={props.name}
            placeholder={props.placeholder}
            defaultValue={props.defaultValue}
            style={props.style}
            value={props.value}
            disabled={props.disabled}
            onChange={
              props.onChange
                ? (e) => props.onChange!(e.target.value)
                : undefined
            }
            onClick={props.onClick}
            onFocus={props.onFocus}
            onBlur={props.onBlur}
            maxLength={400}
            className="min-h-[100px] text-[black] dark:text-[#EEEEEE] resize-none !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080]"
          />
        </FloatLabel>
      </div>
    </Form.Item>
  );
}

export default TextAreaInput;
