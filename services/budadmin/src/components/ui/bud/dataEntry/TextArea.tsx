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
    <div className={`floating-textarea mt-2 ${props.className || ''}`}>
      <FloatLabel
        label={
          <InfoLabel
            text={props.label}
            content={props.info}
            required={props.required}
            classNames="textarea-info-label"
          />
        }
      >
        <Form.Item
          name={props.name}
          rules={props.rules}
          className={props.formItemClassnames}
          hasFeedback
          getValueFromEvent={(e) => {
            props.onChange?.(e.target.value);
            return e.target.value;
          }}
        >
          <TextArea
            placeholder={props.placeholder}
            style={props.style}
            disabled={props.disabled}
            onClick={props.onClick}
            onFocus={props.onFocus}
            onBlur={props.onBlur}
            maxLength={400}
            autoSize={{ minRows: 3, maxRows: 8 }}
            className="!border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080]"
          />
        </Form.Item>
      </FloatLabel>
    </div>
  );
}

export default TextAreaInput;
