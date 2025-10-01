import { v4 as uuidv4 } from 'uuid';
import { Button, Image, Select, Tag } from "antd";
import React, { useEffect, useState } from "react";
import { getChromeColor } from "@/app/components/bud/utils/color";
import SliderInput from "@/app/components/bud/components/input/SliderInput";
import InlineInput from "@/app/components/bud/components/input/InlineInput";
import InlineSwitch from "@/app/components/bud/components/input/InlineSwitch";
import SelectWithAdd from "@/app/components/bud/components/input/SelectWithAdd";
import LabelJSONInput from "@/app/components/bud/components/input/LabelJSONInput";
import { useChatStore } from "@/app/store/chat";

import { Settings } from "@/app/types/chat";
import Notes from './Notes';

interface SettingsListItemProps {
    title: string;
    description: string;
    icon: string;
    children: React.ReactNode;
}


function SettingsListItem(props: SettingsListItemProps) {
    const [open, setOpen] = React.useState(true);

    return (
        <div className="flex flex-col w-full  bg-[#ffffff08] px-[.4rem] py-[.5rem] border-[1px] border-[#1F1F1F] mb-[1rem] rounded-[.5rem]">
            <div
                className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between"
                onClick={() => setOpen(!open)}
            >
                <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
                    <Image
                        src="icons/circle-settings.svg"
                        className={`transform transition-transform ${open ? "rotate-180" : ""
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
                        className={`transform transition-transform ${open ? "" : "rotate-180"
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

export default function SettingsList({chatId}: {chatId: string}) {

    const { settingPresets, addSettingPreset, updateSettingPreset, currentSettingPreset, setCurrentSettingPreset } = useChatStore();
    const [settings, setSettings] = useState<Settings>();
    const [components, setComponents] = useState<SettingsListItemProps[]>([]);
    const [hasHydrated, setHasHydrated] = useState(false);

    useEffect(() => {
        if (typeof window !== "undefined") {
          // Store is now always hydrated since we use custom persistence
          setHasHydrated(true);
        }
      }, []);

    useEffect(() => {
        if (settingPresets.length === 0) {
            const defaultSettings: Settings = {
                id: uuidv4(),
                name: "Default",
                system_prompt: "",
                temperature: 1,
                limit_response_length: false,
                sequence_length: 0,
                context_overflow_policy: "",
                stop_strings: [],
                top_k_sampling: 0,
                repeat_penalty: 0,
                top_p_sampling: 1,
                min_p_sampling: 0,
                enable_structured_json_schema: false,
                is_valid_json_schema: false,
                structured_json_schema: "",
                created_at: new Date().toISOString(),
                modified_at: new Date().toISOString(),
            };
            addSettingPreset(defaultSettings);
            setSettings(defaultSettings);
            setCurrentSettingPreset(defaultSettings);
        } else {
            setSettings(currentSettingPreset);
        }

    }, [hasHydrated, addSettingPreset, currentSettingPreset, setCurrentSettingPreset, settingPresets.length]);

    const handleAddPreset = (name: string) => {
        if (!name) return;
        const newPreset = {
            id: uuidv4(),
            name: name,
            system_prompt: settings?.system_prompt || "",
            temperature: settings?.temperature || 0.5,
            limit_response_length: settings?.limit_response_length || false,
            sequence_length: settings?.sequence_length || 0,
            context_overflow_policy: settings?.context_overflow_policy || "",
            stop_strings: settings?.stop_strings || [],
            top_k_sampling: settings?.top_k_sampling || 0,
            repeat_penalty: settings?.repeat_penalty || 0,
            top_p_sampling: settings?.top_p_sampling || 0,
            min_p_sampling: settings?.min_p_sampling || 0,
            structured_json_schema: settings?.structured_json_schema || "",
            enable_structured_json_schema: settings?.enable_structured_json_schema || false,
            is_valid_json_schema: settings?.is_valid_json_schema || false,
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
        };
        addSettingPreset(newPreset);
        setSettings(newPreset);
    };

    const changePreset = (id: string) => {
        const preset = settingPresets.find((preset) => preset.id === id);
        if (preset) {
            setSettings(preset);
            setCurrentSettingPreset(preset);
        }
    }

    const handleChange = (params: any) => {
        const newSettings = {
            ...settings,
            ...params,
        } as Settings;
        setSettings(newSettings);
        updateSettingPreset(newSettings);
        setCurrentSettingPreset(newSettings);
    };


    const initComponents = React.useCallback(() => {
        const components = [
            {
                title: "Presets",
                description: "Presets",
                icon: "icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem] px-[.5rem]">
                        <SelectWithAdd
                            options={settingPresets}
                            defaultValue={settingPresets[0].name}
                            onChange={changePreset}
                            onAdd={handleAddPreset}
                        />
                    </div>
                ),
            },
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
                            defaultValue={settings?.temperature || 0}
                            value={settings?.temperature || 0}
                            onChange={(value) => handleChange({temperature: value})}
                        />
                        <InlineSwitch
                            title="Limit Response Length"
                            value={settings?.limit_response_length || false}
                            defaultValue={settings?.limit_response_length || false}
                            onChange={(value) =>
                                handleChange({limit_response_length: value})
                            }
                        />
                        {settings?.limit_response_length && <InlineInput
                            title="Sequence Length"
                            value={`${settings?.sequence_length || 0}`}
                            defaultValue={`${settings?.sequence_length || 0}`}
                            type="number"
                            onChange={(value) => handleChange({sequence_length: value})}
                        />}
                    </div>
                ),
            },
            {
                title: "Sampling",
                description: "Notification settings",
                icon: "icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        {/* <InlineInput
                            title="Top K Sampling"
                            value={`${settings?.top_k_sampling || 0}`}
                            defaultValue={`${settings?.top_k_sampling || 0}`}
                            min={0}
                            max={1}
                            type="number"
                            onChange={(value) => handleChange("top_k_sampling", value)}
                        /> */}
                        <InlineInput
                            title="Repeat Penalty"
                            value={`${settings?.repeat_penalty || 0}`}
                            defaultValue={`${settings?.repeat_penalty || 0}`}
                            min={0}
                            max={1}
                            type="number"
                            onChange={(value) => handleChange({repeat_penalty: value})}
                        />
                        {/* <SliderInput
                            title="Top P Sampling"
                            min={0.01}
                            max={1}
                            step={0.01}
                            defaultValue={settings?.top_p_sampling || 0}
                            value={settings?.top_p_sampling || 0}
                            onChange={(value) => handleChange({top_p_sampling: value})}
                        /> */}
                        {/* <SliderInput
                            title="Min P Sampling"
                            min={0.01}
                            max={1}
                            step={0.01}
                            defaultValue={settings?.min_p_sampling || 0}
                            value={settings?.min_p_sampling || 0}
                            onChange={(value) => handleChange("min_p_sampling", value)}
                        /> */}
                    </div>
                ),
            },
            {
                title: "Advanced",
                description: "Notification settings",
                icon: "icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        {/* <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
                            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
                                Context Overflow
                            </span>
                            <div className="flex flex-row items-center gap-[.5rem] w-full max-h-[2rem]">
                                <Select
                                    defaultValue={settings?.context_overflow_policy?.split(
                                        ","
                                    )}
                                    value={settings?.context_overflow_policy?.split(",")}
                                    onChange={(value) =>
                                        handleChange("context_overflow", value)
                                    }
                                    className="customSelect w-full h-full !h-[2rem]"
                                    mode="tags"
                                    tagRender={(props) => (
                                        <Tag
                                            closable
                                            className=" !text-[.625rem] font-[400]  rounded-[0.5rem] !px-[.25rem] !py-[0rem] ml-[.25rem]"
                                            style={{
                                                background: getChromeColor("#D1B854"),
                                                borderColor: getChromeColor("#D1B854"),
                                                color: "#D1B854",
                                            }}
                                            closeIcon={
                                                <Image
                                                    src="icons/close.svg"
                                                    preview={false}
                                                    className="!w-[.625rem] !h-[.425rem]"
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
                        </div> */}

                        <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
                            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
                                Stop Strings
                            </span>
                            <div className="flex flex-row items-center gap-[.5rem] w-full min-w-[7.69rem] max-w-[7.69rem] max-h-[2rem]">
                                <Select
                                    mode="tags"
                                    defaultValue={settings?.stop_strings || []}
                                    value={settings?.stop_strings || []}
                                    onChange={(value) => handleChange({stop_strings: value})}
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
                                                    alt="Close"
                                                    preview={false}
                                                    className="!w-[.625rem] !h-[.625rem]"
                                                />
                                            }
                                        >
                                            {props.label}
                                        </Tag>
                                    )}
                                >
                                    {/* <Select.Option value="Stop">Stop</Select.Option> */}
                                </Select>
                            </div>
                        </div>
                    </div>
                ),
            },

            {
              title: "Structured Output",
              description: "JSON settings",
              icon: "icons/circle-settings.svg",
              children: (
                <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                    <InlineSwitch
                            title="Enable Structured Output"
                            value={settings?.enable_structured_json_schema || false}
                            defaultValue={settings?.enable_structured_json_schema || false}
                            onChange={(value) =>
                                handleChange({enable_structured_json_schema: value})
                            }
                        />
                  {settings?.enable_structured_json_schema && <LabelJSONInput
                    title="JSON Schema"
                    description="Structured Output"
                    placeholder="Enter JSON Schema"
                    value={settings?.structured_json_schema || ""}
                    onChange={(value, valid) => {
                        handleChange({structured_json_schema: value, is_valid_json_schema: valid});
                    }}
                  />}
                </div>
              ),
            },
            {
                title: "Conversation Notes",
                description: "Conversation Notes",
                icon: "icons/circle-settings.svg",
                children: <Notes chatId={chatId} />,
            },
        ];
        setComponents(components);
    }, [settings, settingPresets, changePreset, handleAddPreset, handleChange, chatId]);

    useEffect(() => {
        if (settingPresets.length > 0) {
            initComponents();
        }
    }, [settings, settingPresets.length, initComponents]);


    return (
        <div className="relative flex flex-col w-full h-full overflow-y-auto pb-[5rem] pt-[1rem] px-[1rem]">
            {components?.map((item, index) => (
                <SettingsListItem key={index} {...item} />
            ))}
        </div>
    );
}
