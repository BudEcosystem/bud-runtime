import { v4 as uuidv4 } from 'uuid';
import { Image, Select, Tag } from "antd";
import React, { useEffect, useState, useCallback } from "react";
import { getChromeColor } from "@/utils/color";
import SliderInput from "./input/SliderInput";
import InlineInput from "./input/InlineInput";
import InlineSwitch from "./input/InlineSwitch";
import SelectWithAdd from "./input/SelectWithAdd";
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

interface SettingsProps {
    onClose: () => void;
}

export default function Settings({ onClose }: SettingsProps) {
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
                temperature: 0.7,
                max_tokens: 2000,
                top_p: 1.0,
                frequency_penalty: 0,
                presence_penalty: 0,
                stop_sequences: [],
                seed: 0,
                timeout: 0,
                parallel_tool_calls: true,
                logprobs: false,
                logit_bias: {},
                extra_headers: {},
                max_completion_tokens: 0,
                stream_options: {},
                response_format: {},
                tool_choice: "auto",
                chat_template: "",
                chat_template_kwargs: {},
                mm_processor_kwargs: {},
                created_at: new Date().toISOString(),
                modified_at: new Date().toISOString(),
                modifiedFields: new Set<string>(), // Initialize with empty set
            };
            addSettingPreset(defaultSettings);
            setSettings(defaultSettings);
            setCurrentSettingPreset(defaultSettings);
        } else {
            // Ensure modifiedFields exists when loading from store
            const settingsWithModifiedFields = currentSettingPreset
                ? { ...currentSettingPreset, modifiedFields: currentSettingPreset.modifiedFields || new Set<string>() }
                : null;
            setSettings(settingsWithModifiedFields);
        }
    }, [hasHydrated, addSettingPreset, currentSettingPreset, setCurrentSettingPreset, settingPresets.length]);

    const handleAddPreset = useCallback((name: string) => {
        if (!name) return;
        const newPreset: AgentSettings = {
            id: uuidv4(),
            name: name,
            temperature: settings?.temperature || 0.7,
            max_tokens: settings?.max_tokens || 2000,
            top_p: settings?.top_p || 1.0,
            frequency_penalty: settings?.frequency_penalty || 0,
            presence_penalty: settings?.presence_penalty || 0,
            stop_sequences: settings?.stop_sequences || [],
            seed: settings?.seed || 0,
            timeout: settings?.timeout || 0,
            parallel_tool_calls: settings?.parallel_tool_calls ?? true,
            logprobs: settings?.logprobs ?? false,
            logit_bias: settings?.logit_bias || {},
            extra_headers: settings?.extra_headers || {},
            max_completion_tokens: settings?.max_completion_tokens || 0,
            stream_options: settings?.stream_options || {},
            response_format: settings?.response_format || {},
            tool_choice: settings?.tool_choice || "auto",
            chat_template: settings?.chat_template || "",
            chat_template_kwargs: settings?.chat_template_kwargs || {},
            mm_processor_kwargs: settings?.mm_processor_kwargs || {},
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
            modifiedFields: new Set<string>(settings?.modifiedFields || []), // Copy modifiedFields from current settings
        };
        addSettingPreset(newPreset);
        setSettings(newPreset);
    }, [settings, addSettingPreset]);

    const changePreset = useCallback((id: string) => {
        const preset = settingPresets.find((preset) => preset.id === id);
        if (preset) {
            // Ensure modifiedFields exists when loading a preset
            const presetWithModifiedFields = {
                ...preset,
                modifiedFields: preset.modifiedFields || new Set<string>()
            };
            setSettings(presetWithModifiedFields);
            setCurrentSettingPreset(presetWithModifiedFields);
        }
    }, [settingPresets, setCurrentSettingPreset]);

    const handleChange = useCallback((params: any) => {
        if (!settings) return;

        // Track which fields are being modified
        const modifiedFields = new Set<string>(settings.modifiedFields || []);
        Object.keys(params).forEach(key => {
            modifiedFields.add(key);
        });

        const newSettings = {
            ...settings,
            ...params,
            modified_at: new Date().toISOString(),
            modifiedFields, // Include the updated set of modified fields
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
                            min={0}
                            max={2}
                            step={0.1}
                            defaultValue={settings?.temperature || 0.7}
                            value={settings?.temperature || 0.7}
                            onChange={(value) => handleChange({ temperature: value })}
                        />
                        <InlineInput
                            title="Max Tokens"
                            value={`${settings?.max_tokens || 0}`}
                            defaultValue={`${settings?.max_tokens || 0}`}
                            type="number"
                            onChange={(value) =>
                                handleChange({ max_tokens: Math.max(0, parseInt(value, 10) || 0) })
                            }
                        />
                        <SliderInput
                            title="Top P"
                            min={0}
                            max={1}
                            step={0.1}
                            defaultValue={settings?.top_p || 1.0}
                            value={settings?.top_p || 1.0}
                            onChange={(value) => handleChange({ top_p: value })}
                        />
                    </div>
                ),
            },
            {
                title: "Penalties",
                description: "Penalty settings",
                icon: "/agents/icons/circle-settings.svg",
                children: (
                    <div className="flex flex-col w-full gap-[.5rem] py-[.375rem]">
                        <SliderInput
                            title="Frequency Penalty"
                            min={-2}
                            max={2}
                            step={0.1}
                            defaultValue={settings?.frequency_penalty || 0}
                            value={settings?.frequency_penalty || 0}
                            onChange={(value) => handleChange({ frequency_penalty: value })}
                        />
                        <SliderInput
                            title="Presence Penalty"
                            min={-2}
                            max={2}
                            step={0.1}
                            defaultValue={settings?.presence_penalty || 0}
                            value={settings?.presence_penalty || 0}
                            onChange={(value) => handleChange({ presence_penalty: value })}
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
                                Stop Sequences
                            </span>
                            <div className="flex flex-row items-center gap-[.5rem] w-full min-w-[5.69rem] max-w-[7.69rem]">
                                <Select
                                    mode="tags"
                                    defaultValue={settings?.stop_sequences || []}
                                    value={settings?.stop_sequences || []}
                                    onChange={(value) => handleChange({ stop_sequences: value })}
                                    className="agentSelect w-full "
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
                                                    className="w-[.5rem] h-[.5rem]"
                                                />
                                            }
                                        >
                                            {props.label}
                                        </Tag>
                                    )}
                                />
                            </div>
                        </div>
                        <InlineInput
                            title="Seed"
                            value={`${settings?.seed || 0}`}
                            defaultValue={`${settings?.seed || 0}`}
                            type="number"
                            onChange={(value) =>
                                handleChange({ seed: parseInt(value, 10) || 0 })
                            }
                        />
                        <InlineInput
                            title="Timeout"
                            value={`${settings?.timeout || 0}`}
                            defaultValue={`${settings?.timeout || 0}`}
                            type="number"
                            onChange={(value) =>
                                handleChange({ timeout: Math.max(0, parseInt(value, 10) || 0) })
                            }
                        />
                        <InlineInput
                            title="Max Completion Tokens"
                            value={`${settings?.max_completion_tokens || 0}`}
                            defaultValue={`${settings?.max_completion_tokens || 0}`}
                            type="number"
                            onChange={(value) =>
                                handleChange({ max_completion_tokens: Math.max(0, parseInt(value, 10) || 0) })
                            }
                        />
                        <InlineSwitch
                            title="Parallel Tool Calls"
                            value={settings?.parallel_tool_calls ?? true}
                            defaultValue={settings?.parallel_tool_calls ?? true}
                            onChange={(value) =>
                                handleChange({ parallel_tool_calls: value })
                            }
                        />
                        <InlineSwitch
                            title="Logprobs"
                            value={settings?.logprobs ?? false}
                            defaultValue={settings?.logprobs ?? false}
                            onChange={(value) =>
                                handleChange({ logprobs: value })
                            }
                        />
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
        <div className="relative flex flex-col w-full h-full overflow-y-auto pb-[1rem]">
            <div className="flex items-center justify-between border-b-[1px] border-b-[#1F1F1F] px-[0.9375rem] py-[1.5rem]">
                <Text_16_400_EEEEEE className="leading-[100%]">Model Settings</Text_16_400_EEEEEE>
                <button
                    onClick={onClose}
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
