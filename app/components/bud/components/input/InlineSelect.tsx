import { Image, Select, Tag } from "antd";
import React from "react";
import { getChromeColor } from "../../utils/color";

interface InlineSelectProps {
  title: string;
  value: string;
  defaultValue: string;
  options: string[];
  onChange: (value: string) => void;
}

export default function InlineSelect(props: InlineSelectProps) {
  return (
    <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
      <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
        {props.title}
      </span>
      <div className="flex flex-row items-center gap-[.5rem] w-full">
        <Select
          defaultValue={props.defaultValue}
          onChange={(value) => props.onChange(value)}
          className="w-full"
          mode="tags"
          tagRender={(props) => (
            <Tag
              closable
              className=" !text-[.625rem] font-[400]  rounded-[0.5rem] !p-[.25rem]"
              style={{
                background: getChromeColor("#D1B854"),
                borderColor: getChromeColor("#D1B854"),
                color: "#D1B854",
              }}
              closeIcon={
                <Image
                  src="icons/close.svg"
                  preview={false}
                  className="!w-[.625rem] !h-[.625rem]"
                />
              }
            >
              {props.label}
            </Tag>
          )}
        >
          {props.options.map((option) => (
            <Select.Option key={option} value={option}>
              {option}
            </Select.Option>
          ))}
        </Select>
      </div>
    </div>
  );
}
