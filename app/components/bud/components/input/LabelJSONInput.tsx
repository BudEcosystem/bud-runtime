import React from "react";
import CustomPopover from "../customPopover";
import { Image, Input, Slider } from "antd";
import { Typography } from "antd";
import { JsonInput } from "@mantine/core";
import { errorToast } from "@/app/components/toast";

const { TextArea } = Input;
const { Text } = Typography;

interface LabelJSONInputProps {
  title: string;
  description: string;
  placeholder: string;
  value: string;
  onChange: (value: string, valid: boolean) => void;
  className?: string;
}

export default function LabelJSONInput(props: LabelJSONInputProps) {

  const [valid, setValid] = React.useState(true);
  
  const validateJSON = (value: string) => {
    try {
      JSON.parse(value);
      return true;
    } catch (error) {
      return false;
    }
  };

  const handleChange = (value: string) => {
    const valid = validateJSON(value);
    setValid(valid);
    props.onChange(value, valid);
  };
  return (
    <div
      className={`flex items-start rounded-[6px] relative !bg-[transparent] p-[.5rem]  w-full mb-[0] ${props.className}`}
    >
      <div className="w-full">
        <div className="absolute !bg-[#101010] px-[.25rem] rounded -top-0 left-[.5rem] tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] text-[#EEEEEE] font-[300] text-nowrap">
          {props.title}
          <CustomPopover
            title={props.description}
            classNames="flex items-center"
          >
            <Image
              preview={false}
              src="/icons/info.svg"
              alt="info"
              style={{ width: ".75rem", height: ".75rem" }}
            />
          </CustomPopover>
        </div>
        <TextArea
        className="py-[.65rem]"
        value={props.value}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={props.placeholder}
        autoSize={{ minRows: 3, maxRows: 5 }}
      />
      {!valid && <div className="text-[.75rem] text-[#ff4d4f] font-[300] p-[.25rem] text-nowrap">Invalid JSON</div>}
      </div>
    </div>
  );
}
