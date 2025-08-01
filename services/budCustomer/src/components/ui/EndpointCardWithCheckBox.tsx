import React from "react";
import { Image, Checkbox } from "antd";
import { Text_10_400_B3B3B3, Text_14_400_EEEEEE } from "./text";
import ProjectTags from "@/flows/components/ProjectTags";
import { assetBaseUrl } from "@/components/environment";



type cardProps = {
  data?: any;
  ClassNames?: string;
  selected?: boolean;
  handleClick?: () => void;
};

export default function EndpointCardWithCheckBox({
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
      className={`py-[.85rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex items-start border-box ${ClassNames}`}
    >
      <div className="mr-[1rem] flex flex-col justify-center">
        <div className="bg-[#1F1F1F] w-[2.6875rem] h-[2.6875rem] rounded-[.52rem] flex justify-center items-center grow-0 shrink-0">
          <Image
            preview={false}
            src={(assetBaseUrl + data.model?.icon) || "/images/drawer/zephyr.png"}
            style={{ width: "1.67969rem", height: "1.67969rem" }}
            alt="home"
          />
        </div>
      </div>
      <div className="flex-auto max-w-[87%]">
        <div className="flex items-center justify-between max-w-[100%]">
          <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
            <Text_14_400_EEEEEE className="leading-[100%]">
              {data.name}
            </Text_14_400_EEEEEE>
            <div className="flex justify-start items-center gap-[.5rem]">
              {/* {data.tags.map((item, index) => ( */}
              <ProjectTags
                // key={index}
                name={data.cluster?.name}
                color="#D1B854"
                tagClass="py-[.32rem] "
                textClass="leading-[100%] text-[.625rem] font-[400]"
              />
              <ProjectTags
                // key={index}
                name={`${data.model?.modality}`}
                color="#D1B854"
                tagClass="py-[.32rem] "
                textClass="leading-[100%] text-[.625rem] font-[400]"
              />
              {/* ))} */}
            </div>
          </div>
          <div className="w-[0.875rem] h-[0.875rem]">
            <Checkbox
              style={{
                display: hover || selected ? "flex" : "none",
              }}
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="overflow-hidden truncate max-w-[95%]">
          {data.model?.description}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}
