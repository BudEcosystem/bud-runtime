import { Image, Select, Slider, Switch, Tag, Tooltip } from "antd";
import React from "react";
import { getChromeColor } from "../utils/color";

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
          <div className="flex flex-row items-center gap-[.5rem] p-[.5rem]">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400]">
              Temperature
            </span>
            <Tooltip title="Temperature">
              <Image
                src="icons/info.svg"
                preview={false}
                alt="bud"
                width={".875rem"}
                height={".875rem"}
              />
            </Tooltip>
          </div>
          <div className="flex items-center justify-center mt-[.8rem]">
            <div className="text-[#757575] text-[.75rem] mr-1 ">5</div>
            <Slider
              className="budSlider mt-10 w-full"
              defaultValue={30}
              min={0}
              max={100}
              step={1}
              tooltip={{
                open: true,
                getPopupContainer: (trigger) =>
                  (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
              }}
              styles={{
                track: {
                  backgroundColor: "#965CDE",
                },
                rail: {
                  backgroundColor: "#212225",
                  height: 4,
                },
              }}
            />
            <div className="text-[#757575] text-[.75rem] ml-1">100</div>
          </div>
          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem]">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Limit Response Length
            </span>
            <Switch defaultChecked />
          </div>

          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Sequence Length
            </span>
            <div className="flex flex-row items-center gap-[.5rem]">
              <input
                type="number"
                className="bg-[#101010] text-[#EEEEEE] border-[1px] border-[#1F1F1F] rounded-[0.5rem] p-[.5rem] w-full"
              />
            </div>
          </div>
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
          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Tool K Sampling
            </span>
            <div className="flex flex-row items-center gap-[.5rem]">
              <input
                type="number"
                className="bg-[#101010] text-[#EEEEEE] border-[1px] border-[#1F1F1F] rounded-[0.5rem] p-[.5rem] w-full"
              />
            </div>
          </div>
          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Repeat Penalty
            </span>
            <div className="flex flex-row items-center gap-[.5rem]">
              <input
                type="number"
                className="bg-[#101010] text-[#EEEEEE] border-[1px] border-[#1F1F1F] rounded-[0.5rem] p-[.5rem] w-full"
              />
            </div>
          </div>
          <div className="flex flex-row items-center gap-[.5rem] p-[.5rem]">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400]">
              Top P Sampling
            </span>
            <Tooltip title="Top P Sampling">
              <Image
                src="icons/info.svg"
                preview={false}
                alt="bud"
                width={".875rem"}
                height={".875rem"}
              />
            </Tooltip>
          </div>
          <div className="flex items-center justify-center mt-[.8rem]">
            <div className="text-[#757575] text-[.75rem] mr-1 ">5</div>
            <Slider
              className="budSlider mt-10 w-full"
              defaultValue={30}
              min={0}
              max={100}
              step={1}
              tooltip={{
                open: true,
                getPopupContainer: (trigger) =>
                  (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
              }}
              styles={{
                track: {
                  backgroundColor: "#965CDE",
                },
                rail: {
                  backgroundColor: "#212225",
                  height: 4,
                },
              }}
            />
            <div className="text-[#757575] text-[.75rem] ml-1">100</div>
          </div>
          <div className="flex flex-row items-center gap-[.5rem] p-[.5rem]">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400]">
              Min P Sampling
            </span>
            <Tooltip title="Min P Sampling">
              <Image
                src="icons/info.svg"
                preview={false}
                alt="bud"
                width={".875rem"}
                height={".875rem"}
              />
            </Tooltip>
          </div>
          <div className="flex items-center justify-center mt-[.8rem]">
            <div className="text-[#757575] text-[.75rem] mr-1 ">5</div>
            <Slider
              className="budSlider mt-10 w-full"
              defaultValue={30}
              min={0}
              max={100}
              step={1}
              tooltip={{
                open: true,
                getPopupContainer: (trigger) =>
                  (trigger.parentNode as HTMLElement) || document.body, // Cast parentNode to HTMLElement
              }}
              styles={{
                track: {
                  backgroundColor: "#965CDE",
                },
                rail: {
                  backgroundColor: "#212225",
                  height: 4,
                },
              }}
            />
            <div className="text-[#757575] text-[.75rem] ml-1">100</div>
          </div>
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
