import React from "react";
import { ConfigProvider, Form, FormRule, Input } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import type { DatePickerProps } from "antd";
import { DatePicker } from "antd";
import dayjs from "dayjs";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (dateString: string) => void;
  name: string;
  label: string;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
  ClassNames?: string;
  InputClasses?: string;
  style?: React.CSSProperties;
  rules?: FormRule[];
  suffix?: React.ReactNode;
  defaultValue?: string;
}

function CustomDatepicker(props: BudInputProps) {
  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      className="mb-0"
      hasFeedback
    >
      <div className={`floating-textarea ${props.ClassNames}`}>
        <FloatLabel
          classNames={`mx-[.2rem] floatingLabel`}
          label={
            <InfoLabel
              required={props.rules?.some((rule: any) => rule.required)}
              text={props.label}
              content={"Explain the project in detail"}
            />
          }
        >
          <ConfigProvider
            theme={{
              components: {
                DatePicker: {
                  activeBg: "#00000000",
                  activeBorderColor: "#CFCFCF",
                },
              },
              token: {
                colorBorder: "#757575",
              },
            }}
          >
            <DatePicker
              getPopupContainer={() => document.body}
              format={"MM/DD/YYYY"}
              value={props.value ? dayjs(props.value, "MM/DD/YYYY") : null}
              onChange={((date, dateString) => {
                if (typeof dateString === "string") {
                  props.onChange?.(dateString);
                }
              }) as DatePickerProps['onChange']}
              className={`w-[100%] bg-[transparent] !border py-[.6rem] !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] ${props.InputClasses}`}
            />
          </ConfigProvider>
        </FloatLabel>
      </div>
    </Form.Item>
  );
}


export default CustomDatepicker;
