import React from "react";
import { Form, FormRule, Input, Image } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import CustomPopover from "@/flows/components/customPopover";
import { useTheme } from "@/context/themeContext";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  name: string;
  label?: string;
  value?: any;
  defaultValue?: any;
  placeholder?: string;
  disabled?: boolean;
  allowOnlyNumbers?: boolean;
  preventFirstSpace?: boolean;
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
  const { effectiveTheme } = useTheme();
  const isLight = effectiveTheme === "light";

  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      className={`${props.formItemClassnames}`}
      hasFeedback
    >
      <div className={`floating-textarea ${props.ClassNames}`}>
        {props.label ? (
          <div className="relative">
            <div
              className={`absolute px-[.2rem] left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap text-[.75rem] font-[400] h-[3px] pl-[.35rem] pr-[.55rem]`}
              style={{
                background: isLight ? "#ffffff" : "#0d0d0d",
                color: isLight ? "#1a1a1a" : "#EEEEEE",
                top: "-2px",
              }}
            >
              {props.label}{" "}
              {props.rules?.some((rule: any) => rule.required) && (
                <b className="text-[#FF4D4F]">*</b>
              )}
              {props.infoText && (
                <CustomPopover title={props.infoText}>
                  <Image
                    className="mt-[.1rem] cursor-pointer"
                    preview={false}
                    src="/images/drawer/info.png"
                    alt="info"
                    style={{ width: ".75rem", pointerEvents: "auto" }}
                  />
                </CustomPopover>
              )}
            </div>
            <Input
              name={props.name}
              placeholder={props.placeholder}
              value={props.value}
              defaultValue={
                props.value === undefined ? props.defaultValue : undefined
              }
              style={{
                ...props.style,
                paddingTop: ".75rem",
                paddingBottom: ".75rem",
                paddingLeft: ".5rem",
                paddingRight: "1rem",
              }}
              disabled={props.disabled}
              onChange={(e) => {
                let newValue = e.target.value;
                if (props.allowOnlyNumbers) {
                  newValue = newValue.replace(/[^0-9]/g, "");
                }
                props.onChange?.(newValue);
              }}
              onKeyDown={(e) => {
                // Prevent space as first character if preventFirstSpace is true
                if (
                  props.preventFirstSpace &&
                  e.key === " " &&
                  e.currentTarget.value.length === 0
                ) {
                  e.preventDefault();
                }
                props.onKeyDown?.(e);
              }}
              suffix={props.suffix}
              type={props.type}
              className={`text-[black] dark:text-[#EEEEEE] border border-[#B1B1B1] dark:border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] ${props.InputClasses}`}
            />
          </div>
        ) : (
          <Input
            name={props.name}
            placeholder={props.placeholder}
            value={props.value}
            defaultValue={
              props.value === undefined ? props.defaultValue : undefined
            }
            style={{
              ...props.style,
              paddingTop: ".75rem",
              paddingBottom: ".75rem",
              paddingLeft: ".5rem",
              paddingRight: "1rem",
            }}
            disabled={props.disabled}
            onChange={(e) => {
              let newValue = e.target.value;
              if (props.allowOnlyNumbers) {
                newValue = newValue.replace(/[^0-9]/g, "");
              }
              props.onChange?.(newValue);
            }}
            onKeyDown={(e) => {
              // Prevent space as first character if preventFirstSpace is true
              if (
                props.preventFirstSpace &&
                e.key === " " &&
                e.currentTarget.value.length === 0
              ) {
                e.preventDefault();
              }
              props.onKeyDown?.(e);
            }}
            suffix={props.suffix}
            type={props.type}
            className={`border border-[#B1B1B1] dark:border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300] ${props.InputClasses}`}
          />
        )}
      </div>
    </Form.Item>
  );
}

export default TextInput;
