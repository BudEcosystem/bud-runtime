import React from "react";
import { Popover } from "antd";
import { Text_12_400_EEEEEE } from "./text";

export const TEXT_TRUNCATION_LENGTH = 25;

interface TruncatedTextCellProps {
  text: string;
  truncationLength?: number;
}

export function TruncatedTextCell({
  text,
  truncationLength = TEXT_TRUNCATION_LENGTH
}: TruncatedTextCellProps) {
  if (!text || text === "-") {
    return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
  }

  const needsTruncation = text.length > truncationLength;
  const truncatedText = needsTruncation
    ? text.substring(0, truncationLength) + "..."
    : text;

  if (needsTruncation) {
    return (
      <Popover
        content={
          <div className="max-w-[300px] break-words p-[.8rem]">
            <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
          </div>
        }
        placement="top"
      >
        <div
          className="cursor-pointer"
          style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          <Text_12_400_EEEEEE>{truncatedText}</Text_12_400_EEEEEE>
        </div>
      </Popover>
    );
  }

  return (
    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
      <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
    </div>
  );
}

export default TruncatedTextCell;
