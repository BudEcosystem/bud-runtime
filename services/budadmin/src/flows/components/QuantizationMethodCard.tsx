import { assetBaseUrl } from "@/components/environment";
import { Text_10_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import { Input, Image, Checkbox } from "antd"; // Added Checkbox import
import React from "react";
import Tags from "./DrawerTags";

type cardProps = {
  data?: any,
  ClassNames?: string;
  selected?: boolean;
  handleClick?: () => void;
};


export default function QuantizationMethodCard({ data, ClassNames, selected, handleClick }: cardProps) {
    const [hover, setHover] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className={`py-[1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.5rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box ${ClassNames}`}
    >
      <div className="flex-auto">
        <div className="flex items-center justify-between h-4 max-w-[100%]">
          <div className="flex justify-between">
            <Text_14_400_EEEEEE className="">{data.name}</Text_14_400_EEEEEE>
          </div>
          <div>
            <Checkbox
              style={{
                display: hover || selected ? "flex" : "none",
              }}
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] mt-[.85rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="py-[.3rem] max-w-[95%]">
          {data.description}
        </Text_10_400_B3B3B3>
        <div className="flex flex-row flex-wrap gap-[0.375rem] row-gap-[0.375rem]">
          <Tags name={`Quantisation Hardware: ${data.hardware_support}`} color={'#479D5F'} textClass="text-[.625rem]" />
            <Tags name={`Quantisation Type: ${data.method_type}`} color={'#D1B854'} textClass="text-[.625rem]" />
            <Tags name={`Runtime Hardware: ${data.runtime_hardware_support}`} color={'#965CDE'} textClass="text-[.625rem]" />
          </div>
      </div>
    </div>
  );
}
