import React from "react";
import CustomPopover from "../CustomPopover";
import { Image, Input } from "antd";
import { errorToast } from "@/components/toast";

const { TextArea } = Input;

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
  const [localValue, setLocalValue] = React.useState(props.value || '');

  const validateJSON = (value: string) => {
    try {
      JSON.parse(value);
      return true;
    } catch (error) {
      return false;
    }
  };

  const handleBlur = () => {
    const valid = validateJSON(localValue);
    setValid(valid);
    props.onChange(localValue, valid);
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setLocalValue(e.target.value);
    setValid(validateJSON(e.target.value));
  };

  return (
    <div
      className={`flex items-start rounded-[6px] relative !bg-[transparent] p-[.5rem] w-full mb-[0] ${props.className}`}
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
          value={localValue}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder={props.placeholder}
          autoSize={{ minRows: 3, maxRows: 5 }}
        />
        {!valid && <div className="text-[.75rem] text-[#ff4d4f] font-[300] p-[.25rem] text-nowrap">Invalid JSON</div>}
      </div>
    </div>
  );
}
