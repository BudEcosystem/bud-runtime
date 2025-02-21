import { Image } from "antd";
import React from "react";

interface SettingsListItemProps {
  title: string;
  description: string;
  icon: string;
  children: React.ReactNode;
}

function SettingsListItem(props: SettingsListItemProps) {
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
            {props.title}
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
      <div>{open && props.children}</div>
    </div>
  );
}

interface SettingsListProps {
  data: any[];
}

function SettingsList({ data }: SettingsListProps) {

  const components = [
    {
      title: "General",
      description: "General settings",
      icon: "icons/circle-settings.svg",
      children: (
        <div className="flex flex-col w-full gap-[1rem] py-[.5rem]">
          <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Language
            </span>
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              English
            </span>
          </div>
          <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Theme
            </span>
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Dark
            </span>
          </div>
        </div>
      ),
    },
    {
      title: "Notifications",
      description: "Notification settings",
      icon: "icons/circle-settings.svg",
      children: (
        <div className="flex flex-col w-full gap-[1rem] py-[.5rem]">
          <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Email
            </span>
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Enabled
            </span>
          </div>
          <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Push
            </span>
            <span className="text-[#B3B3B3] text-[.75rem] font-[400]">
              Enabled
            </span>
          </div>
        </div>
      ),
    },

  ]

  return (
    <div className="flex flex-col w-full h-full bg-[#101010]  ">
      {components?.map((item, index) => (
        <SettingsListItem key={index} {...item} />
      ))}
    </div>
  );
}

export default SettingsList;
