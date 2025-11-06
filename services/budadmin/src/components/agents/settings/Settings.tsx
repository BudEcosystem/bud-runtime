import { v4 as uuidv4 } from 'uuid';
import { Button, Image, Select, Tag } from "antd";
import React, { useEffect, useState, useCallback } from "react";
import { getChromeColor } from "@/utils/color";
import SliderInput from "./input/SliderInput";
import InlineInput from "./input/InlineInput";
import InlineSwitch from "./input/InlineSwitch";
import SelectWithAdd from "./input/SelectWithAdd";
import LabelJSONInput from "./input/LabelJSONInput";
import { useAgentStore, AgentSettings } from "@/stores/useAgentStore";
import { Text_16_400_EEEEEE } from '@/components/ui/text';

interface SettingsListItemProps {
    title: string;
    description: string;
    icon: string;
    children: React.ReactNode;
}

function SettingsListItem(props: SettingsListItemProps) {
    const [open, setOpen] = React.useState(true);

    return (
        <div className="flex flex-col w-full bg-[#ffffff08] px-[.4rem] py-[.5rem] border-[1px] border-[#1F1F1F] mb-[1rem] rounded-[.5rem]">
            <div
                className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
                onClick={() => setOpen(!open)}
            >
                <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
                    <Image
                        src="/agents/icons/circle-settings.svg"
                        className={`transform transition-transform ${open ? "rotate-180" : ""}`}
                        preview={false}
                        alt="settings"
                        width={".75rem"}
                        height={".75rem"}
                    />
                    <span className="text-[#B3B3B3] text-[.75rem] font-[400] pt-[.05rem]">
                        {props.title}
                    </span>
                </div>
                <div className="flex flex-row items-center gap-[1rem] p-[.5rem]">
                    <Image
                        src="/agents/icons/chevron-down.svg"
                        className={`transform transition-transform ${open ? "" : "rotate-180"}`}
                        preview={false}
                        alt="chevron"
                        width={".875rem"}
                        height={".875rem"}
                    />
                </div>
            </div>
            <div>{open && props.children}</div>
        </div>
    );
}

export default function Settings() {
    const { settingPresets, addSettingPreset, updateSettingPreset, currentSettingPreset, setCurrentSettingPreset } = useAgentStore();
    const [settings, setSettings] = useState<AgentSettings | null>(null);
    const [components, setComponents] = useState<SettingsListItemProps[]>([]);
    const [hasHydrated, setHasHydrated] = useState(false);

    useEffect(() => {
        if (typeof window !== "undefined") {
            setHasHydrated(true);
        }
    }, []);

    useEffect(() => {
        if (settingPresets.length === 0) {
            const defaultSettings: AgentSettings = {
                id: uuidv4(),
                name: "Default",
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

    const handleAddPreset = useCallback((name: string) => {
        if (!name) return;
        const newPreset: AgentSettings = {
            id: uuidv4(),
            name: name,
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
    }, [settings, addSettingPreset]);

    const changePreset = useCallback((id: string) => {
        const preset = settingPresets.find((preset) => preset.id === id);
        if (preset) {
            setSettings(preset);
            setCurrentSettingPreset(preset);
        }
    }, [settingPresets, setCurrentSettingPreset]);

    const handleChange = useCallback((params: any) => {
        if (!settings) return;
        const newSettings = {
            ...settings,
            ...params,
            modified_at: new Date().toISOString(),
        } as AgentSettings;
        setSettings(newSettings);
        updateSettingPreset(newSettings);
        setCurrentSettingPreset(newSettings);
    }, [settings, updateSettingPreset, setCurrentSettingPreset]);

    const initComponents = React.useCallback(() => {
        const components = [
            {
                title: "Presets",
                description: "Presets",
                icon: "/agents/icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem] px-[.5rem]">
                        <SelectWithAdd
                            options={settingPresets}
                            defaultValue={settingPresets[0]?.name}
                            onChange={changePreset}
                            onAdd={handleAddPreset}
                        />
                    </div>
                ),
            },
            {
                title: "Basic",
                description: "General settings",
                icon: "/agents/icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        <SliderInput
                            title="Temperature"
                            min={0.1}
                            max={1}
                            step={0.1}
                            defaultValue={settings?.temperature || 0}
                            value={settings?.temperature || 0}
                            onChange={(value) => handleChange({ temperature: value })}
                        />
                        <InlineSwitch
                            title="Limit Response Length"
                            value={settings?.limit_response_length || false}
                            defaultValue={settings?.limit_response_length || false}
                            onChange={(value) =>
                                handleChange({ limit_response_length: value })
                            }
                        />
                        {settings?.limit_response_length && (
                            <InlineInput
                                title="Sequence Length"
                                value={`${settings?.sequence_length || 0}`}
                                defaultValue={`${settings?.sequence_length || 0}`}
                                type="number"
                                onChange={(value) =>
                                    handleChange({ sequence_length: Math.max(0, parseInt(value, 10) || 0) })
                                }
                            />
                        )}
                    </div>
                ),
            },
            {
                title: "Sampling",
                description: "Sampling settings",
                icon: "/agents/icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        <InlineInput
                            title="Repeat Penalty"
                            value={`${settings?.repeat_penalty || 0}`}
                            defaultValue={`${settings?.repeat_penalty || 0}`}
                            min={0}
                            max={1}
                            type="number"
                            onChange={(value) =>
                                handleChange({ repeat_penalty: Math.min(1, Math.max(0, parseFloat(value) || 0)) })
                            }
                        />
                    </div>
                ),
            },
            {
                title: "Advanced",
                description: "Advanced settings",
                icon: "/agents/icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        <div className="flex flex-row items-center gap-[.625rem] p-[.5rem] w-full">
                            <span className="text-[#EEEEEE] text-[.75rem] font-[400] text-nowrap w-full">
                                Stop Strings
                            </span>
                            <div className="flex flex-row items-center gap-[.5rem] w-full min-w-[7.69rem] max-w-[7.69rem] max-h-[2rem]">
                                <Select
                                    mode="tags"
                                    defaultValue={settings?.stop_strings || []}
                                    value={settings?.stop_strings || []}
                                    onChange={(value) => handleChange({ stop_strings: value })}
                                    className="customSelect w-full h-full !h-[2rem]"
                                    tagRender={(props) => (
                                        <Tag
                                            closable
                                            className="!text-[.625rem] font-[400] rounded-[0.5rem] !p-[.25rem] ml-[.25rem]"
                                            style={{
                                                background: getChromeColor("#D1B854"),
                                                borderColor: getChromeColor("#D1B854"),
                                                color: "#D1B854",
                                            }}
                                            closeIcon={
                                                <Image
                                                    src="/agents/icons/close.svg"
                                                    alt="Close"
                                                    preview={false}
                                                    className="!w-[.625rem] !h-[.625rem]"
                                                />
                                            }
                                        >
                                            {props.label}
                                        </Tag>
                                    )}
                                />
                            </div>
                        </div>
                    </div>
                ),
            },
            {
                title: "Structured Output",
                description: "JSON settings",
                icon: "/agents/icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        <InlineSwitch
                            title="Enable Structured Output"
                            value={settings?.enable_structured_json_schema || false}
                            defaultValue={settings?.enable_structured_json_schema || false}
                            onChange={(value) =>
                                handleChange({ enable_structured_json_schema: value })
                            }
                        />
                        {settings?.enable_structured_json_schema && (
                            <LabelJSONInput
                                title="JSON Schema"
                                description="Structured Output"
                                placeholder="Enter JSON Schema"
                                value={settings?.structured_json_schema || ""}
                                onChange={(value, valid) => {
                                    handleChange({ structured_json_schema: value, is_valid_json_schema: valid });
                                }}
                            />
                        )}
                    </div>
                ),
            },
        ];
        setComponents(components);
    }, [settings, settingPresets, changePreset, handleAddPreset, handleChange]);

    useEffect(() => {
        if (settingPresets.length > 0) {
            initComponents();
        }
    }, [settings, settingPresets.length, initComponents]);

    return (
        <div className="relative flex flex-col w-full h-full overflow-y-auto pb-[5rem]">
            <div className="flex items-center justify-between border-b-[1px] border-b-[#1F1F1F] px-[0.9375rem] py-[1.5rem]">
                <Text_16_400_EEEEEE className="leading-[100%]">Model Settings</Text_16_400_EEEEEE>
                <button
                    className="text-[#B3B3B3] hover:text-[#FFFFFF] transition-colors"
                >
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="18"
                        height="18"
                        viewBox="0 0 18 18"
                        fill="none"
                    >
                        <path
                            d="M13.5 4.5L4.5 13.5M4.5 4.5L13.5 13.5"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        />
                    </svg>
                </button>
            </div>
            <div className='px-[1rem] pt-[.75rem]'>
                {components?.map((item, index) => (
                    <SettingsListItem key={index} {...item} />
                ))}
            </div>
        </div>
    );
}
