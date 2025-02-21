import { Image } from "antd";
import React from "react";

function SettingsListItem() {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="flex flex-col w-full  bg-[#101010] px-[1rem] py-[.5rem] border-[1px] border-[#1F1F1F] ">
      <div
        className="flex flex-row items-center gap-[1rem] py-[.5rem] justify-between"
        onClick={() => setOpen(!open)}
      >
        <div className="flex flex-row items-center gap-[.5rem] p-[.5rem]">
          <Image
            src="icons/circle-settings.svg"
            className={`transform transition-transform ${
              open ? "rotate-180" : ""
            }`}
            preview={false}
            alt="bud"
            width={".875rem"}
            height={".875rem"}
          />
          <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
            System information
          </span>
        </div>
        <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
          <Image
            src="icons/chevron-down.svg"
            className={`transform transition-transform ${
              open ? "" : "rotate-180"
            }`}
            preview={false}
            alt="bud"
            width={".875rem"}
            height={".875rem"}
          />
        </div>
      </div>
      <div>
        {open && (
          <div className="flex flex-col gap-[.5rem] p-[.5rem]">
            <div className="flex flex-row items-center gap-[1rem]">
              <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
                System information
              </span>
              <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
                System information
              </span>
            </div>
            <div className="flex flex-row items-center gap-[1rem]">
              <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
                System information
              </span>
              <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
                System information
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface SettingsListProps {
  data: any[];
}

function SettingsList({ data }: SettingsListProps) {
  return (
    <div className="flex flex-col w-full h-full bg-[#101010]  ">
      {data?.map((item, index) => (
        <SettingsListItem key={index} />
      ))}
    </div>
  );
}

export default SettingsList;
