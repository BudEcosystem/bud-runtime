import { Box, Flex } from "@radix-ui/themes";
import React from "react";
import { Text_14_400_EEEEEE } from "../../text";

function DrawerTitleCard({
  title,
  description,
  classNames,
  descriptionClass,
  descriptionTextClass,
}: {
  title: string;
  description: string;
  classNames?: string;
  descriptionClass?: string;
  descriptionTextClass?: string;
}) {
  if (!title && !description) {
    return null;
  }

  return (
    <div
      className={`px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#B1B1B1] dark:border-b-[#1F1F1F] ${classNames}`}
      style={{
        paddingTop: "1.1rem",
        paddingBottom: ".9rem",
      }}
    >
      <div className="flex justify-between align-center">
        <Text_14_400_EEEEEE className="p-0 pt-[.4rem] m-0 !text-black dark:!text-[#EEEEEE]">
          {title}
        </Text_14_400_EEEEEE>
      </div>
      <div
        className={`${descriptionClass}`}
        style={{
          paddingTop: ".55rem",
        }}
      >
        <div
          className={`block text-xs font-normal leading-[180%] !text-black dark:!text-[#757575] ${descriptionTextClass || ""}`}
        >
          {description}
        </div>
      </div>
    </div>
  );
}

export default DrawerTitleCard;
