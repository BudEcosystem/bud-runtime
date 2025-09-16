import React from "react";
import { Form, FormRule, Select, ConfigProvider, Image } from "antd";
import { Text_12_300_EEEEEE } from "@/components/ui/text";
import CustomPopover from "./customPopover";

export interface SelectInputProps {
  name: string;
  label: string;
  value?: any;
  placeholder?: string;
  disabled?: boolean;
  ClassNames?: string;
  SelectClasses?: string;
  formItemClassnames?: string;
  style?: React.CSSProperties;
  rules?: FormRule[];
  infoText?: string;
  options: Array<{ label: string; value: string }>;
  onChange?: (value: any) => void;
  mode?: "multiple" | "tags";
  tagRender?: (props: any) => React.ReactElement;
  suffixIcon?: React.ReactNode;
}

function SelectInput(props: SelectInputProps) {
  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      className={props.formItemClassnames}
      hasFeedback
    >
      <div
        className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0] ${props.ClassNames}`}
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute h-[3px] bg-[#0d0d0d] top-[0rem] left-[.75rem] px-[0.025rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap bg-[#0d0d0d] pl-[.35rem] pr-[.55rem]">
            {props.label}
            {props.rules?.some((rule: any) => rule.required) && (
              <b className="text-[#FF4D4F]">*</b>
            )}
            {props.infoText && (
              <CustomPopover title={props.infoText}>
                <Image
                  src="/images/info.png"
                  preview={false}
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            )}
          </Text_12_300_EEEEEE>
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
          <ConfigProvider
            theme={{
              token: {
                colorTextPlaceholder: "#808080",
              },
            }}
          >
            <Select
              placeholder={props.placeholder}
              style={{
                backgroundColor: "transparent",
                color: "#EEEEEE",
                border: "0.5px solid #757575",
                width: "100%",
                ...props.style,
              }}
              disabled={props.disabled}
              size="large"
              className={`drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] outline-none ${props.SelectClasses}`}
              options={props.options}
              onChange={props.onChange}
              mode={props.mode}
              tagRender={props.tagRender}
              suffixIcon={
                props.suffixIcon || (
                  <Image
                    src="/images/icons/dropD.png"
                    preview={false}
                    alt="dropdown"
                    style={{ width: "auto", height: "auto" }}
                  />
                )
              }
            />
          </ConfigProvider>
        </div>
      </div>
    </Form.Item>
  );
}

export default SelectInput;
