import { Image, Select, Tag } from "antd";
import React from "react";
import { getChromeColor } from "../utils/color";
import SliderInput from "../components/input/SliderInput";
import InlineInput from "../components/input/InlineInput";
import InlineSwitch from "../components/input/InlineSwitch";

interface SettingsListItemProps {
  title: string;
  description: string;
  icon: string;
  children: React.ReactNode;
}

function SettingsListItem(props: SettingsListItemProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="flex flex-col w-full  bg-[#101010] px-[.4rem] py-[.5rem] border-[0px] border-b-[1px] border-[#1F1F1F] ">
      <div
        className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between"
        onClick={() => setOpen(!open)}
      >
        <div className="flex flex-row items-center gap-[.4rem] p-[.5rem]">
          <Image
            src="icons/circle-settings.svg"
            className={`transform transition-transform ${
              open ? "rotate-180" : ""
            }`}
            preview={false}
            alt="bud"
            width={".75rem"}
            height={".75rem"}
          />
          <span className="text-[#B3B3B3] text-[.75rem] font-[400] pt-[.05rem]">
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
      title: "Basic",
      description: "General settings",
      icon: "icons/circle-settings.svg",
      children: (
        <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
          <SliderInput
            title="Temperature"
            min={0}
            max={100}
            step={1}
            defaultValue={30}
            value={30}
            onChange={(value) => console.log(value)}
          />
          <InlineSwitch
            title="Limit Response Length"
            value={true}
            defaultValue={true}
            onChange={(value) => console.log(value)}
          />
          <InlineInput
            title="Sequence Length"
            value="30"
            defaultValue="30"
            type="number"
            onChange={(value) => console.log(value)}
          />
        </div>
      ),
    },
    {
      title: "Advanced",
      description: "Notification settings",
      icon: "icons/circle-settings.svg",
      children: (
        <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Context Overflow
            </span>
            <div className="flex flex-row items-center gap-[.5rem] w-full">
              <Select
                defaultValue="Select"
                className="w-full"
                mode="tags"
                tagRender={(props) => (
                  <Tag
                    closable
                    className=" !text-[.625rem] font-[400]  rounded-[0.5rem] !p-[.25rem]"
                    style={{
                      background: getChromeColor("#D1B854"),
                      borderColor: getChromeColor("#D1B854"),
                      color: "#D1B854",
                    }}
                    closeIcon={
                      <Image
                        src="icons/close.svg"
                        preview={false}
                        className="!w-[.625rem] !h-[.625rem]"
                      />
                    }
                  >
                    {props.label}
                  </Tag>
                )}
              >
                <Select.Option value="Select">Select</Select.Option>
              </Select>
            </div>
          </div>

          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Stop Strings
            </span>
            <div className="flex flex-row items-center gap-[.5rem] w-full">
              <Select defaultValue="Select" className="w-full">
                <Select.Option value="Select">Select</Select.Option>
              </Select>
            </div>
          </div>
        </div>
      ),
    },
    {
      title: "Sampling",
      description: "Notification settings",
      icon: "icons/circle-settings.svg",
      children: (
        <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
          <InlineInput
            title="Tool K Sampling"
            value="30"
            defaultValue="30"
            type="number"
            onChange={(value) => console.log(value)}
          />
          <InlineInput
            title="Repeat Penalty"
            value="30"
            defaultValue="30"
            type="number"
            onChange={(value) => console.log(value)}
          />
          <SliderInput
            title="Top P Sampling"
            min={5}
            max={100}
            step={1}
            defaultValue={30}
            value={30}
            onChange={(value) => console.log(value)}
          />
          <SliderInput
            title="Min P Sampling"
            min={5}
            max={100}
            step={1}
            defaultValue={30}
            value={30}
            onChange={(value) => console.log(value)}
          />
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col w-full h-full bg-[#101010]  overflow-y-auto pb-[5rem]">
      {components?.map((item, index) => (
        <SettingsListItem key={index} {...item} />
      ))}
    </div>
  );
}

export default SettingsList;
