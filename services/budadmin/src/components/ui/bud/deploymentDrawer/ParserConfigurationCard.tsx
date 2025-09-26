import { Checkbox } from "antd";
import React from "react";

interface ParserCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  selected: boolean;
  onChange: (checked: boolean) => void;
}

function ParserConfigurationCard({
  title,
  description,
  icon,
  selected,
  onChange,
}: ParserCardProps) {
  const [hover, setHover] = React.useState(false);


  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={() => onChange(!selected)}
      className="py-[1.1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box"
    >
      <div className="mr-[.7rem]">
        <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[5px] flex justify-center items-center shrink-0 grow-0">
          {icon}
        </div>
      </div>
      <div className="flex justify-between w-full items-center">
        <div className="flex flex-col">
          <div className="text-[#EEEEEE] text-[0.875rem] leading-[150%]">
            {title}
          </div>
          <div className="text-[#757575] text-[0.625rem] leading-[150%]">
            {description}
          </div>
        </div>
        <div
          style={{
            display: hover || selected ? "flex" : "none",
          }}
        >
          <Checkbox
            checked={selected}
            onChange={(e) => onChange(e.target.checked)}
            onClick={(e) => e.stopPropagation()}
            className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
          />
        </div>
      </div>
    </div>
  );
}

export default ParserConfigurationCard;
