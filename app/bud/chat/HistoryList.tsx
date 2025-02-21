import { Image } from "antd";
import React from "react";

function HistoryListItem() {
  return (
    <div className="flex flex-row items-center gap-[1rem] p-[.5rem] justify-between">
      <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
        <Image
          src="icons/list-item.svg"
          alt="bud"
          width={".875rem"}
          height={".875rem"}
        />
        <span className="text-[#EEE] text-[.875rem] font-[400]">
          Unnamed Chat
        </span>
      </div>

      <span className="text-[#757575] text-[.625rem] font-[400]">
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
    <div className="flex flex-col w-full h-full bg-[#101010] px-[1.5rem] py-[1rem]">
      {data?.map((item, index) => (
        <HistoryListItem key={index} />
      ))}
    </div>
  );
}

export default HistoryList;
