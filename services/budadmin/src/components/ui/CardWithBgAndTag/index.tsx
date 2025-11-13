import React from "react";
import {
  Text_15_600_EEEEEE,
  Text_16_400_FFFFFF,
  Text_38_400_EEEEEE,
} from "../text";
import { Image } from "antd";
import Tags from "src/flows/components/DrawerTags";

export type GeneralCardsProps = {
  name: string;
  bg?: string;
  value?: string | number;
  tag?: {
    value: string;
    tagColor: string;
  };
  ClassNames?: string;
  valueClassNames?: string;
};

const CardWithBgAndTag: React.FC<GeneralCardsProps> = ({
  name,
  bg,
  value,
  tag,
  ClassNames,
  valueClassNames,
}) => {
  return (
    <div
      className={`relative rounded-[8px] px-[1.6rem] border-[1.5px] border-[#1c1c1c] bg-[#101010] ${ClassNames}`}
      style={{
        width: "32%",
        minHeight: "172px",
        paddingTop: "2rem",
        paddingBottom: "1.5rem",
      }}
    >
      {/* Background Image */}
      <div className="absolute inset-0 z-0">
        <Image
          preview={false}
          src={bg}
          alt="background"
          className="w-full h-full object-cover"
        />
      </div>

      {/* Content */}
      <div className="relative z-10 w-full h-full flex flex-col justify-start">
        <Text_15_600_EEEEEE>{name}</Text_15_600_EEEEEE>
        <div
          className={`${valueClassNames}`}
          style={{
            paddingTop: "2.2rem",
          }}
        >
          <Text_38_400_EEEEEE>{value}</Text_38_400_EEEEEE>
        </div>
        {tag && (
          <div className="flex mt-[.85rem]">
            <Tags
              name={tag.value}
              color={tag.tagColor}
              textClass="text-[0.8125rem]"
              classNames="!py-[.2rem]"
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default CardWithBgAndTag;
