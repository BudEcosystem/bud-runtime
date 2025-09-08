import React from "react";
import { ConfigProvider, Form, FormRule, Select, Image } from "antd";
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE } from "@/components/ui/text";
import CustomPopover from "@/flows/components/customPopover";
import { useTheme } from "@/context/themeContext";

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
  required?: boolean;
  ClassNames?: string;
  classNames?: string;
  InputClasses?: string;
  style?: React.CSSProperties;
  rules?: FormRule[];
  suffix?: React.ReactNode;
  defaultValue?: string;
  selectOptions?: any;
}

function CustomSelect(props: BudInputProps) {
  const { effectiveTheme } = useTheme();
  const isLight = effectiveTheme === "light";

  return (
    <div
      className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0] hover:bg-[#FFFFFF08] ${props.ClassNames}`}
    >
      {props.label && (
        <div className="w-full">
          <div
            className={`absolute px-[.2rem]  left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap text-[.75rem] font-[400] h-[3px] pl-[.35rem] pr-[.55rem] ${props.classNames}`}
            style={{
              background: isLight ? "#ffffff" : "#0d0d0d",
              color: isLight ? "#1a1a1a" : "#EEEEEE",
            }}
          >
            {props.label} {props.required && <b className="text-[#FF4D4F]">*</b>}
            {props.info && (
              <CustomPopover title={props.info}>
                <Image
                  className="mt-[.1rem]"
                  preview={false}
                  src="/images/drawer/info.png"
                  alt="info"
                  style={{ width: ".75rem" }}
                />
              </CustomPopover>
            )}
          </div>
        </div>
      )}
      <div className="custom-select-two bud-custom-select w-full rounded-[6px] relative">
        <ConfigProvider
          theme={{
            token: {
              colorTextPlaceholder: '#808080',
              colorText: isLight ? '#1a1a1a' : '#EEEEEE',
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
            className={`drawerInp !bg-[transparent] !text-[#1a1a1a] dark:!text-[#EEEEEE] font-[300] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#CFCFCF] focus:border-[#CFCFCF] active:border-[#CFCFCF] ${props.InputClasses}`}
            options={props.selectOptions}
            onChange={(value) => {
              props.onChange?.(value)
            }}
            popupClassName="bud-custom-select-dropdown"
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
