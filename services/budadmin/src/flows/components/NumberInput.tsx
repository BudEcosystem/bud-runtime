import React from "react";
import { Form, FormRule, Input } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { InputNumber } from "antd";

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
  ClassNames?: string;
  InputClasses?: string;
  formItemClassnames?: string;
  style?: React.CSSProperties;
  rules: FormRule[];
  suffix?: React.ReactNode;
  defaultValue?: string;
  infoText?: string;
  type?: string;
}

function NumberInput(props: BudInputProps) {
  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      hasFeedback
      className={`${props.formItemClassnames}`}
    >
      <div className={`floating-textarea ${props.ClassNames}`}>
        <FloatLabel
          label={
            <InfoLabel
              required={props.rules.some((rule: any) => rule.required)}
              text={props.label}
              content={props.infoText || props.placeholder}
            />
          }
        >
          <InputNumber
            defaultValue={props.defaultValue}
            name={props.name}
            placeholder={props.placeholder}
            style={{
              ...props.style,
              paddingTop: "1rem",
              paddingBottom: "1rem",
            }}
            type={props.type}
            disabled={props.disabled}
            value={props.value}
            onChange={
              props.onChange
                ? (value) => {
                    props.onChange && props.onChange(value);
                  }
                : undefined
            }
            suffix={props.suffix}
            className={`border border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] ${props.InputClasses}`}
          />
        </FloatLabel>
      </div>
    </Form.Item>
  );
}

export default NumberInput;
