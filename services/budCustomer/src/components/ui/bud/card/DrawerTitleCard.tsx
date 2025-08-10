import { Box, Flex } from "@radix-ui/themes";
import React from "react";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "../../text";

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
      className={`px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F] ${classNames}`}
      style={{
        paddingTop: "1.1rem",
        paddingBottom: ".9rem",
      }}
    >
      <div className="flex justify-between align-center">
        <Text_14_400_EEEEEE className="p-0 pt-[.4rem] m-0">
          {title}
        </Text_14_400_EEEEEE>
      </div>
      <div
        className={`${descriptionClass}`}
        style={{
          paddingTop: ".55rem",
        }}
      >
        <Text_12_400_757575
          className={`${descriptionTextClass ? descriptionTextClass : "leading-[180%]"}`}
        >
          {description}
        </Text_12_400_757575>
      </div>
    </div>
  );
}

export default DrawerTitleCard;
