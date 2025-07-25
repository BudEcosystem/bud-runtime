import React from "react";
import { Form, FormRule, Input } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  name: string;
  label: string;
  value?: string;
  info?: string;
  placeholder?: string;
  disabled?: boolean;
  ClassNames?: string;
  InputClasses?:string;
  style?: React.CSSProperties;
  rules?: FormRule[];
  suffix?: React.ReactNode;
  defaultValue?: string;
  readOnly?: boolean;
}

function CustomInput(props: BudInputProps) {
  return (
    <Form.Item name={props.name} rules={props.rules} className="mb-0"  hasFeedback>
      <div className={`floating-textarea ${props.ClassNames}`}>
        <FloatLabel 
          classNames={`mx-[.2rem] floatingLabel`}
          label={<InfoLabel
          required={props.rules.some((rule: any) => rule.required)}
          text={props.label} content={props.info || ''} />}>
          <Input
            readOnly={props.readOnly}
            defaultValue={props.defaultValue}
            name={props.name}
            placeholder={props.placeholder}
            style={props.style}
            disabled={props.disabled}
            value={props.value}
            onChange={(e) => {
              props.onChange && props.onChange(e.target.value);
            }}
            suffix={props.suffix}
            className={`!border py-[.6rem] !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] ${props.InputClasses}`}
          />
        </FloatLabel>
      </div>
    </Form.Item>
  );
}

export default CustomInput;