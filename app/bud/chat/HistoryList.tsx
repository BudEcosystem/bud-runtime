import { Image } from "antd";
import React from "react";

function HistoryListItem() {
  return (
    <div className="flex flex-row items-center gap-[1rem] p-[.45rem] px-[.65rem] justify-between border-[1px] border-[#1F1F1F] rounded-[8px] backdrop-blur-[10px]">
      <div className="flex flex-row items-center gap-[.6rem] px-[.27rem]">
        <Image
          src="icons/list-item.svg"
          alt="bud"
          width={".875rem"}
          height={".875rem"}
        />
        <span className="Lato-Regular text-[#EEE] text-[.875rem] font-[400]">
          Unnamed Chat
        </span>
      </div>

      <span className="Open-Sans text-[#757575] text-[.625rem] font-[400] pr-[.15rem]">
        265 Tokens
      </span>
    </div>
  );
}

interface HistoryListProps {
    data: any[];
}

function HistoryList({ data }: HistoryListProps) {
  return (
    <div className="flex flex-col w-full h-[41%] bg-[#101010] px-[.9rem] py-[.95rem] gap-y-[.6rem]">
      {data?.map((item, index) => (
        <HistoryListItem key={index} />
      ))}
    </div>
  );
}

export default HistoryList;
