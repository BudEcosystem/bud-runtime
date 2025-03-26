import { Button, Image, Select, Tag } from "antd";
import React, { useContext, useEffect } from "react";
import { getChromeColor } from "../utils/color";
import SliderInput from "../components/input/SliderInput";
import InlineInput from "../components/input/InlineInput";
import InlineSwitch from "../components/input/InlineSwitch";
import ChatContext from "@/app/context/ChatContext";
import RootContext from "@/app/context/RootContext";
import LabelTextArea from "../components/input/LabelTextArea";
import { useNotes } from "../hooks/useNotes";
import Notes from "./Notes";

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
  const { handleSettingsChange } = useContext(RootContext);
  const { chat } = useContext(ChatContext);

  const handleChange = (chat: any, key: string, value: any) => {
    handleSettingsChange(chat, key, value);
  };


  const components = [
    {
      title: "Basic",
      description: "General settings",
      icon: "icons/circle-settings.svg",
      children: (
        <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
          <SliderInput
            title="Temperature"
            min={0.1}
            max={1}
            step={0.1}
            defaultValue={chat?.chat_setting?.temperature || 0}
            value={chat?.chat_setting?.temperature || 0}
            onChange={(value) => handleChange(chat, "temperature", value)}
          />
          <InlineSwitch
            title="Limit Response Length"
            defaultValue={chat?.chat_setting?.limit_response_length || true}
            onChange={(value) =>
              handleChange(chat, "limit_response_length", value)
            }
          />
          <InlineInput
            title="Sequence Length"
            value={`${chat?.chat_setting?.sequence_length || 0}`}
            defaultValue={`${chat?.chat_setting?.sequence_length || 0}`}
            type="number"
            onChange={(value) => handleChange(chat, "sequence_length", value)}
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
            <div className="flex flex-row items-center gap-[.5rem] w-full  min-w-[7.69rem] max-w-[7.69rem] max-h-[2rem]">
              <Select
                defaultValue={chat?.chat_setting?.context_overflow_policy?.split(
                  ","
                )}
                value={chat?.chat_setting?.context_overflow_policy?.split(",")}
                onChange={(value) =>
                  handleChange(chat, "context_overflow", value)
                }
                className="customSelect w-full h-full !h-[2rem]"
                mode="tags"
                tagRender={(props) => (
                  <Tag
                    closable
                    className=" !text-[.625rem] font-[400]  rounded-[0.5rem] !p-[.25rem] ml-[.25rem]"
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
                <Select.Option value="allow">Allow</Select.Option>
                <Select.Option value="deny">Deny</Select.Option>
              </Select>
            </div>
          </div>

          <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
              Stop Strings
            </span>
            <div className="flex flex-row items-center gap-[.5rem] w-full min-w-[7.69rem] max-w-[7.69rem] max-h-[2rem]">
              <Select
                mode="tags"
                defaultValue={chat?.chat_setting?.stop_strings || []}
                value={chat?.chat_setting?.stop_strings || []}
                onChange={(value) => handleChange(chat, "stop_strings", value)}
                className="customSelect w-full h-full !h-[2rem]"
                tagRender={(props) => (
                  <Tag
                    closable
                    className=" !text-[.625rem] font-[400]  rounded-[0.5rem] !p-[.25rem]  ml-[.25rem]"
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
                <Select.Option value="Stop">Stop</Select.Option>
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
            title="Top K Sampling"
            value={`${chat?.chat_setting?.top_k_sampling || 0}`}
            defaultValue={`${chat?.chat_setting?.top_k_sampling || 0}`}
            min={0}
            max={1}
            type="number"
            onChange={(value) => handleChange(chat, "top_k_sampling", value)}
          />
          <InlineInput
            title="Repeat Penalty"
            value={`${chat?.chat_setting?.repeat_penalty || 0}`}
            defaultValue={`${chat?.chat_setting?.repeat_penalty || 0}`}
            min={0}
            max={1}
            type="number"
            onChange={(value) => handleChange(chat, "repeat_penalty", value)}
          />
          <SliderInput
            title="Top P Sampling"
            min={0.01}
            max={1}
            step={0.01}
            defaultValue={chat?.chat_setting?.top_p_sampling || 0}
            value={chat?.chat_setting?.top_p_sampling || 0}
            onChange={(value) => handleChange(chat, "top_p_sampling", value)}
          />
          <SliderInput
            title="Min P Sampling"
            min={0.01}
            max={1}
            step={0.01}
            defaultValue={chat?.chat_setting?.min_p_sampling || 0}
            value={chat?.chat_setting?.min_p_sampling || 0}
            onChange={(value) => handleChange(chat, "min_p_sampling", value)}
          />
        </div>
      ),
    },
    {
      title: "Conversation Notes",
      description: "Conversation Notes",
      icon: "icons/circle-settings.svg",
      children: (
        <Notes />
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
