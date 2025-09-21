import { assetBaseUrl } from "@/components/environment";
import { Text_10_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import { Input, Image, Checkbox } from "antd"; // Added Checkbox import
import React from "react";

type cardProps = {
  data?: any;
  ClassNames?: string;
  selected?: boolean;
  handleClick?: () => void;
};

function ProviderCardWithCheckBox({
  data,
  ClassNames,
  selected,
  handleClick,
}: cardProps) {
  const [hover, setHover] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className={`py-[1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box ${ClassNames}`}
    >
      <div className="mr-[.7rem] flex flex-col justify-center">
        <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0">
          <Image
            preview={false}
            src={
              data.iconLocal
                ? `${data.icon}`
                : `${assetBaseUrl}${data.icon || data.logo_url}`
            }
            className="!w-[1.25rem] !h-[1.25rem]"
            style={{ width: "1.25rem", height: "1.25rem" }}
            alt="home"
          />
        </div>
      </div>
      <div className="flex-auto max-w-[91%]">
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
        <Text_10_400_B3B3B3 className="overflow-hidden truncate pt-[.3rem] max-w-[95%]">
          {data.description}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

export default ProviderCardWithCheckBox;
