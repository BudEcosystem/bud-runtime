import React from "react";
import { Form, FormRule, Input } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { EyeInvisibleOutlined, EyeOutlined } from "@ant-design/icons";


interface BudInputPasswordProps {
  name: string;
  label: string;
  placeholder?: string;
  rules: any[];
  value?: string;
  defaultValue?: string;
  readOnly?: boolean;
  disabled?: boolean;
  onChange?: (value: string) => void;
  suffix?: React.ReactNode;
  style?: React.CSSProperties;
  ClassNames?: string;
  InputClasses?: string;
  inputStyle?: React.CSSProperties;
}

export const CustomPasswordInput: React.FC<BudInputPasswordProps> = (props) => {
  return (
    <Form.Item name={props.name} rules={props.rules} className="mb-0" hasFeedback>
      <div className={`floating-textarea ${props.ClassNames}`}>
        <FloatLabel
          classNames="mx-[.2rem] floatingLabel"
          label={
            <InfoLabel
              required={props.rules?.some((rule: any) => rule.required)}
              text={props.label}
              content="Explain the project in detail"
            />
          }
        >
          <Input.Password
            readOnly={props.readOnly}
            defaultValue={props.defaultValue}
            name={props.name}
            placeholder={props.placeholder}
            style={props.style}
            disabled={props.disabled}
            value={props.value}
            onChange={(e) => props.onChange?.(e.target.value)}
            iconRender={(visible) => visible ? <span><EyeOutlined className="text-[#B3B3B3]" /></span> : <span><EyeInvisibleOutlined className="text-[#B3B3B3]" /></span>}
            className={`!border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] ${props.InputClasses}`}
            styles={{
              input: {
                paddingTop: ".6rem",
                paddingBottom: ".6rem",
                ...props.inputStyle,
              },
            }}
            suffix={props.suffix}
          />
        </FloatLabel>
      </div>
    </Form.Item>
  );
};