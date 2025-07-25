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
  value?: any;
  placeholder?: string;
  disabled?: boolean;
  allowOnlyNumbers?: boolean;
  ClassNames?: string;
  InputClasses?: string;
  formItemClassnames?: string;
  style?: React.CSSProperties;
  rules: FormRule[];
  suffix?: React.ReactNode;
  infoText?: string;
  type?: string;
}

function TextInput(props: BudInputProps) {
  // When used inside Form.Item, we need to accept value and onChange from Form.Item
  const FormItemInput = ({ value = '', onChange, ...restProps }: any) => {
    const inputProps: any = {
      value: value,
      name: props.name,
      placeholder: props.placeholder,
      style: {
        ...props.style,
        paddingTop: ".75rem",
        paddingBottom: ".75rem",
        paddingLeft: ".5rem",
        paddingRight: "1rem",
      },
      disabled: props.disabled,
      onChange: (e) => {
        let newValue = e.target.value;
        if (props.allowOnlyNumbers) {
          newValue = newValue.replace(/[^0-9]/g, "");
        }
        // Call Form.Item's onChange
        onChange?.(newValue);
        // Call custom onChange if provided
        props.onChange?.(newValue);
      },
      suffix: props.suffix,
      type: props.type,
      className: `border border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] ${props.InputClasses}`,
    };

    return (
      <div className={`floating-textarea ${props.ClassNames}`}>
        <FloatLabel
          label={
            <InfoLabel
              required={props.rules?.some((rule: any) => rule.required)}
              text={props.label}
              content={props.infoText || props.placeholder}
            />
          }
          value={value}
        >
          <Input {...inputProps} />
        </FloatLabel>
      </div>
    );
  };

  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      validateTrigger="onChange"
      hasFeedback
      className={`${props.formItemClassnames}`}
    >
      <FormItemInput />
    </Form.Item>
  );
}

export default TextInput;
