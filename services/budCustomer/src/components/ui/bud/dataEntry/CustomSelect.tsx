import React from "react";
import { ConfigProvider, Form, FormRule, Select, Image } from "antd";
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE } from "@/components/ui/text";
import CustomPopover from "@/flows/components/customPopover";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: string) => void;
  name: string;
  label?: string;
  info?: string;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
  ClassNames?: string;
  InputClasses?: string;
  style?: React.CSSProperties;
  rules?: FormRule[];
  suffix?: React.ReactNode;
  defaultValue?: string;
  selectOptions?: any;
}

function CustomSelect(props: BudInputProps) {
  return (
    <div
      className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0] hover:bg-[#FFFFFF08] ${props.ClassNames}`}
    >
      {props.label && (
        <div className="w-full">
          <Text_12_400_EEEEEE className={`absolute px-[.2rem] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap floatingLabel`}>
            {props.label}
            <CustomPopover title={props.info} >
              <Image
                src="/images/info.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </CustomPopover>
          </Text_12_400_EEEEEE>
        </div>
      )}
      <div className="custom-select-two w-full rounded-[6px] relative">
        <ConfigProvider
          theme={{
            token: {
              colorTextPlaceholder: '#808080',
            },
          }}
        >
          <Select
            placeholder={props.placeholder}
            style={{
              backgroundColor: "transparent",
              border: "0.5px solid #757575",
              width: "100%",
              paddingTop: '.6rem',
              paddingBottom: '.6rem',
              fontSize: '.75rem'
            }}
            value={props.value || null}
            size="large"
            className={`drawerInp !bg-[transparent] text-[black] dark:text-[#EEEEEE] font-[300] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#CFCFCF] focus:border-[#CFCFCF] active:border-[#CFCFCF] ${props.InputClasses}`}
            options={props.selectOptions}
            onChange={(value) => {
              props.onChange?.(value)
            }}
            suffixIcon={
              <img
                src={`/icons/customArrow.png`}
                alt="custom arrow"
                style={{ width: '10px', height: '7px' }}
              />
            }
          />
        </ConfigProvider>
      </div>
    </div>
  );
}

export default CustomSelect;
