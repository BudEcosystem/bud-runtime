import { Image } from "antd";
import React from "react";

export type Session = {
  id: string;
  name: string;
  total_tokens: number;
  created_at: string;
  modified_at: string;
};

function HistoryListItem({
  data,
}: {
  data: Session;
}
) {
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
          {data.name}
        </span>
      </div>

      <span className="Open-Sans text-[#757575] text-[.625rem] font-[400] pr-[.15rem]">
        {data.total_tokens} tokens
      </span>
    </div>
  );
}

interface HistoryListProps {
    data: Session[];
}

function HistoryList({ data }: HistoryListProps) {
  return (
    <div className="flex flex-col w-full h-[41%] bg-[#101010] px-[.9rem] py-[.95rem] gap-y-[.6rem]">
      {data?.map((item, index) => (
        <HistoryListItem key={index} data={item} />
      ))}
      {data?.length === 0 && (
        <div className="flex flex-row items-center justify-center w-full h-[2.5rem] bg-[#101010] rounded-[8px] border-[1px] border-[#1F1F1F] backdrop-blur-[10px]">
          <span className="Open-Sans text-[#757575] text-[.625rem] font-[400]">
            No chat history
          </span>
        </div>
      )}
    </div>
  );
}

export default HistoryList;
