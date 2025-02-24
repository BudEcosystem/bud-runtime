import React from "react";
import CustomPopover from "../customPopover";
import { Image, Input, Slider } from "antd";

interface LabelInputProps {
  title: string;
  description: string;
  value: string;
  onChange: (value: string) => void;
}

export default function LabelInput(props: LabelInputProps) {
  return (
    <div
      className={`flex items-start rounded-[6px] relative !bg-[transparent]  w-[48%] mb-[0]`}
    >
      <div className="w-full">
        <div className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] text-[#EEEEEE] font-[300] text-nowrap">
          {props.title}
          <CustomPopover title={props.description}>
            <Image
              preview={false}
              src="/images/info.png"
              alt="info"
              style={{ width: ".75rem", height: ".75rem" }}
            />
          </CustomPopover>
        </div>
      </div>
      <Input
        type="number"
        placeholder="Enter value"
        style={{
          backgroundColor: "transparent",
          color: "#EEEEEE",
          border: "0.5px solid #757575",
        }}
        min={1}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        size="large"
        className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
      />
    </div>
  );
}
