"use client";
import React, { useState, useEffect, useMemo } from "react";
import { Tabs, Tag, Image, ConfigProvider, Drawer, Breadcrumb } from "antd";
import type { TabsProps } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import ModelTags from "@/components/ui/ModelTags";
import dayjs from "dayjs";
import { Model } from "@/hooks/useModels";
import { successToast } from "@/components/toast";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_14_400_757575,
  Text_12_400_5B6168,
  Text_12_400_787B83
} from "@/components/ui/text";

interface ModelDetailDrawerProps {
  visible: boolean;
  onClose: () => void;
  model: Model | null;
}

const ModelDetailDrawer: React.FC<ModelDetailDrawerProps> = ({
  visible,
  onClose,
  model,
}) => {
  const [isMinimized, setIsMinimized] = useState(false);

  const handleMinimize = () => {
    setIsMinimized(true);
    // Add animation class for minimize effect
    const drawer = document.querySelector('.drawerRoot');
    if (drawer) {
      drawer.classList.add('hide-drawer');
    }
    // Close after animation
    setTimeout(() => {
      onClose();
      setIsMinimized(false);
    }, 300);
  };

  return (
    <Drawer
      open={visible}
      onClose={onClose}
      width={520}
      closable={false}
      className="drawerRoot"
      styles={{
        wrapper: {
          borderRadius: "17px",
          overflow: "hidden",
        },
        body: {
          padding: 0,
          height: "100%",
          display: "flex",
          flexDirection: "column",
        },
      }}
      maskClassName="bud-drawer-mask"
    >
      <div className="drawerBackground flex flex-col h-full">
        {model && <ModelDetailContent model={model} onClose={onClose} onMinimize={handleMinimize} />}
      </div>
    </Drawer>
  );
};

const ModelDetailContent: React.FC<{ model: Model; onClose: () => void; onMinimize: () => void }> = ({
  model,
  onClose,
  onMinimize,
}) => {
  const [filteredItems, setFilteredItems] = useState<TabsProps["items"]>([]);
  const assetBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    successToast("Copied to clipboard");
  };

  const getModelIcon = (model: any) => {
    if (model.icon) {
      const iconUrl = model.icon.startsWith("http")
        ? model.icon
        : `${assetBaseUrl}/${model.icon.startsWith("/") ? model.icon.slice(1) : model.icon}`;
      return { type: "url", value: iconUrl };
    }

    const name = model.name?.toLowerCase() || "";
    if (name.includes("gpt"))
      return { type: "icon", value: "simple-icons:openai" };
    if (name.includes("claude"))
      return { type: "icon", value: "simple-icons:anthropic" };
    if (name.includes("llama"))
      return { type: "icon", value: "simple-icons:meta" };
    if (name.includes("dall")) return { type: "icon", value: "ph:image" };
    if (name.includes("whisper"))
      return { type: "icon", value: "ph:microphone" };

    return { type: "icon", value: "ph:robot" };
  };

  const GeneralTab = () => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isOverflowing, setIsOverflowing] = useState(false);
    const descriptionRef = React.useRef<HTMLDivElement>(null);

    const toggleDescription = () => setIsExpanded(!isExpanded);

    useEffect(() => {
      if (descriptionRef.current) {
        const element = descriptionRef.current;
        setIsOverflowing(element.scrollHeight > 60);
      }
    }, [model?.description]);

    return (
      <div className="space-y-5">
        {/* Description */}
        {model?.description && (
          <div>
            <div
              ref={descriptionRef}
              className={`${
                isExpanded ? "" : "line-clamp-3"
              } overflow-hidden`}
            >
              <Text_12_400_B3B3B3 className="leading-[180%]">
                {model?.description}
              </Text_12_400_B3B3B3>
            </div>
            {isOverflowing && (
              <div className="flex justify-end mt-2">
                <Text_12_600_EEEEEE
                  className="cursor-pointer text-[#89C0F2] hover:text-[#6BA8E0] transition-colors"
                  onClick={toggleDescription}
                >
                  {isExpanded ? "See less" : "See more"}
                </Text_12_600_EEEEEE>
              </div>
            )}
          </div>
        )}

        {/* Basic Information */}
        <div>
          <Text_14_500_EEEEEE className="mb-3">
            Basic Information
          </Text_14_500_EEEEEE>
          <div className="bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3>Model Name</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right">{model.name}</Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3>Source</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right">{model.source || "N/A"}</Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3>Model Size</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right">
                {model.model_size ? `${model.model_size}B` : "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3>Provider Type</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right">
                {model.provider_type === "cloud_model" ? "Cloud" : "Local"}
              </Text_12_400_EEEEEE>
            </div>
          </div>
        </div>

        {/* Modalities */}
        <div>
          <Text_14_500_EEEEEE>Modalities</Text_14_500_EEEEEE>
          <Text_12_400_757575 className="mt-1 mb-3">
            Input and output capabilities of the model
          </Text_12_400_757575>
          <div className="flex gap-3">
            <div className="flex flex-col items-center gap-3 bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] w-[50%] p-4 rounded-lg">
              <Text_14_400_EEEEEE>Input</Text_14_400_EEEEEE>
              <div className="flex justify-center items-center gap-3">
                <Image
                  preview={false}
                  src={
                    model.modality.text.input
                      ? "/images/drawer/endpoints/text.png"
                      : "/images/drawer/endpoints/text-not.png"
                  }
                  alt={model.modality.text.label}
                  style={{ width: "1.25rem", height: "1.25rem" }}
                />
                <Image
                  preview={false}
                  src={
                    model.modality.image.input
                      ? "/images/drawer/endpoints/image.png"
                      : "/images/drawer/endpoints/image-not.png"
                  }
                  alt={model.modality.image.label}
                  style={{ width: "1.25rem", height: "1.25rem" }}
                />
                <Image
                  preview={false}
                  src={
                    model.modality.audio.input
                      ? "/images/drawer/endpoints/audio_speech.png"
                      : "/images/drawer/endpoints/audio_speech-not.png"
                  }
                  alt={model.modality.audio.label}
                  style={{ width: "1.25rem", height: "1.25rem" }}
                />
              </div>
              <Text_12_400_EEEEEE className="text-center">
                {[
                  model.modality.text.input && model.modality.text.label,
                  model.modality.image.input && model.modality.image.label,
                  model.modality.audio.input && model.modality.audio.label,
                ]
                  .filter(Boolean)
                  .join(", ")}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex flex-col items-center gap-3 bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] w-[50%] p-4 rounded-lg">
              <Text_14_400_EEEEEE>Output</Text_14_400_EEEEEE>
              <div className="flex justify-center items-center gap-3">
                <Image
                  preview={false}
                  src={
                    model.modality.text.output
                      ? "/images/drawer/endpoints/text.png"
                      : "/images/drawer/endpoints/text-not.png"
                  }
                  alt={model.modality.text.label}
                  style={{ width: "1.25rem", height: "1.25rem" }}
                />
                <Image
                  preview={false}
                  src={
                    model.modality.image.output
                      ? "/images/drawer/endpoints/image.png"
                      : "/images/drawer/endpoints/image-not.png"
                  }
                  alt={model.modality.image.label}
                  style={{ width: "1.25rem", height: "1.25rem" }}
                />
                <Image
                  preview={false}
                  src={
                    model.modality.audio.output
                      ? "/images/drawer/endpoints/audio_speech.png"
                      : "/images/drawer/endpoints/audio_speech-not.png"
                  }
                  alt={model.modality.audio.label}
                  style={{ width: "1.25rem", height: "1.25rem" }}
                />
              </div>
              <Text_12_400_EEEEEE className="text-center">
                {[
                  model.modality.text.output && model.modality.text.label,
                  model.modality.image.output && model.modality.image.label,
                  model.modality.audio.output && model.modality.audio.label,
                ]
                  .filter(Boolean)
                  .join(", ")}
              </Text_12_400_EEEEEE>
            </div>
          </div>
        </div>

        {/* Supported Endpoints */}
        <div>
          <Text_14_500_EEEEEE>Supported Endpoints</Text_14_500_EEEEEE>
          <Text_12_400_757575 className="mt-1 mb-3">
            Available API endpoints for this model
          </Text_12_400_757575>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(model.supported_endpoints).map(([key, value]) => {
              const iconName = value.enabled
                ? `${key}.png`
                : `${key}-not.png`;
              return (
                <div
                  key={key}
                  className="flex items-center gap-3 bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] p-3 rounded-lg"
                >
                  <Image
                    preview={false}
                    src={`/images/drawer/endpoints/${iconName}`}
                    alt={value.label}
                    style={{ height: "1.25rem", width: "1.25rem" }}
                    onError={(e) => {
                      e.currentTarget.src = value.enabled
                        ? "/images/drawer/endpoints/default.png"
                        : "/images/drawer/endpoints/default-not.png";
                    }}
                  />
                  <div className="flex-1 min-w-0">
                    {value.enabled ? (
                      <>
                        <Text_14_400_EEEEEE className="truncate">{value.label}</Text_14_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="truncate">
                          {value.path}
                        </Text_12_400_B3B3B3>
                      </>
                    ) : (
                      <>
                        <Text_14_400_757575 className="truncate">{value.label}</Text_14_400_757575>
                        <Text_12_400_757575 className="truncate">
                          {value.path}
                        </Text_12_400_757575>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Model URI */}
        {model.uri && (
          <div>
            <Text_14_500_EEEEEE className="mb-3">
              Model URI
            </Text_14_500_EEEEEE>
            <div className="bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] rounded-lg p-4">
              <div className="flex items-center justify-between gap-3">
                <Text_12_400_EEEEEE className="font-mono truncate flex-1">
                  {model.uri}
                </Text_12_400_EEEEEE>
                <button
                  onClick={() => copyToClipboard(model.uri)}
                  className="text-[#757575] hover:text-[#EEEEEE] transition-colors shrink-0"
                >
                  <CopyOutlined />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tags */}
        {model.tags && model.tags.length > 0 && (
          <div>
            <Text_14_500_EEEEEE className="mb-3">Tags</Text_14_500_EEEEEE>
            <div className="flex flex-wrap gap-2">
              {model.tags.map((tag, index) => (
                <Tag
                  key={index}
                  className="bg-[rgba(255,255,255,0.027)] text-[#EEEEEE] border-[#1F1F1F]"
                >
                  {tag.name}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* Strengths */}
        {model?.strengths?.length > 0 && (
          <div>
            <Text_14_500_EEEEEE>Model is Great at</Text_14_500_EEEEEE>
            <Text_12_400_757575 className="mt-1 mb-3">
              Key strengths and capabilities
            </Text_12_400_757575>
            <div className="bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] rounded-lg p-4">
              <ul className="space-y-2">
                {model?.strengths?.map((item: any, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-[#89C0F2] mt-1">•</span>
                    <Text_12_400_EEEEEE className="leading-relaxed">
                      {item}
                    </Text_12_400_EEEEEE>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Limitations */}
        {model?.limitations?.length > 0 && (
          <div>
            <Text_14_500_EEEEEE>Model is Not Good With</Text_14_500_EEEEEE>
            <Text_12_400_757575 className="mt-1 mb-3">
              Known limitations and constraints
            </Text_12_400_757575>
            <div className="bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] rounded-lg p-4">
              <ul className="space-y-2">
                {model?.limitations?.map((item: any, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-[#757575] mt-1">•</span>
                    <Text_12_400_EEEEEE className="leading-relaxed">
                      {item}
                    </Text_12_400_EEEEEE>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    );
  };

  const items: TabsProps["items"] = useMemo(
    () => [
      {
        key: "1",
        label: "General",
        children: <GeneralTab />,
      },
    ],
    [model],
  );

  useEffect(() => {
    setFilteredItems(items);
  }, [model, items]);

  const onChange = () => {
    // Handle tab change if needed
  };

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header with close and minimize buttons matching drawer pattern */}
      <div className="ant-header-breadcrumb">
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onClose();
            }}
            className="hover:opacity-80 transition-opacity"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="hover:text-[#FFFFFF] mr-.5"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M13.8103 5.09188C14.0601 4.8421 14.0601 4.43712 13.8103 4.18734C13.5606 3.93755 13.1556 3.93755 12.9058 4.18734L8.99884 8.0943L5.09188 4.18734C4.8421 3.93755 4.43712 3.93755 4.18734 4.18734C3.93755 4.43712 3.93755 4.8421 4.18734 5.09188L8.0943 8.99884L4.18734 12.9058C3.93755 13.1556 3.93755 13.5606 4.18734 13.8103C4.43712 14.0601 4.8421 14.0601 5.09188 13.8103L8.99884 9.90338L12.9058 13.8103C13.1556 14.0601 13.5606 14.0601 13.8103 13.8103C14.0601 13.5606 14.0601 13.1556 13.8103 12.9058L9.90338 8.99884L13.8103 5.09188Z"
                fill="#B3B3B3"
              />
            </svg>
          </button>
          <button
            onClick={() => {
              onMinimize();
            }}
            className="hover:opacity-80 transition-opacity"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="hover:text-[#FFFFFF] mr-4"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M15.5654 14.748C16.104 15.2866 15.2856 16.1044 14.747 15.5665L11.1293 11.9481V13.9429C11.1293 14.7044 9.972 14.7044 9.972 13.9429L9.9727 10.5517C9.9727 10.2325 10.2322 9.97302 10.5514 9.97302H13.9433C14.7048 9.97302 14.7048 11.1304 13.9433 11.1304L11.9478 11.1297L15.5654 14.748ZM7.6123 4.79945C7.6123 4.03796 8.76965 4.03796 8.76965 4.79945V8.19137C8.76965 8.51058 8.5102 8.77003 8.19099 8.77003L4.79907 8.76933C4.03758 8.76933 4.03758 7.61198 4.79907 7.61198H6.79383L3.17619 3.99434C2.63759 3.45574 3.45603 2.638 3.99463 3.1759L7.61227 6.79354L7.6123 4.79945Z"
                fill="#B3B3B3"
              />
            </svg>
          </button>
        </div>
        {/* Breadcrumb navigation */}
        <Breadcrumb
          separator={<Text_12_400_5B6168 className="mx-2">/</Text_12_400_5B6168>}
          items={[
            {
              title: (
                <Text_12_400_787B83 className="cursor-default text-[#EEEEEE]">
                  Models
                </Text_12_400_787B83>
              ),
            },
            {
              title: (
                <Text_12_400_787B83 className="cursor-default text-[#EEEEEE]">
                  {model?.name || "Model Details"}
                </Text_12_400_787B83>
              ),
            },
          ]}
        />
      </div>

      {/* Content wrapper with scrolling */}
      <div className="flex-1 overflow-y-auto scrollBox">
        <div className="form-layout mx-[2.6rem] my-[1.1rem] bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-[#1F1F1F] rounded-[6px]">
          {/* Title card with model info */}
          <DrawerTitleCard
            title={model?.name || "Model Details"}
            description=""
            descriptionClass="hidden"
          />

          {/* Model icon and tags */}
          <DrawerCard classNames="pb-4">
            <div className="flex items-start justify-start gap-4">
              <div className="shrink-0 grow-0 flex items-center justify-center">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#89C0F2]/20 to-[#89C0F2]/10 flex items-center justify-center">
                  {(() => {
                    const iconData = getModelIcon(model);
                    return iconData.type === "url" ? (
                      <img
                        src={iconData.value}
                        alt={model.name}
                        className="w-6 h-6 object-contain"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                        }}
                      />
                    ) : (
                      <Icon
                        icon={iconData.value}
                        className="text-[#89C0F2] text-[1.5rem]"
                      />
                    );
                  })()}
                </div>
              </div>
              <div className="flex-1">
                <ModelTags model={model} maxTags={3} limit={true} />
                <div className="flex items-center gap-2 mt-2">
                  <Icon
                    icon="ph:calendar"
                    className="text-[#757575] text-[0.875rem]"
                  />
                  <Text_12_400_B3B3B3>Created on&nbsp;&nbsp;</Text_12_400_B3B3B3>
                  <Text_12_400_EEEEEE>
                    {dayjs(model.created_at).format("DD MMM, YYYY")}
                  </Text_12_400_EEEEEE>
                </div>
              </div>
            </div>
          </DrawerCard>

          {/* Tabs content */}
          <DrawerCard classNames="pt-0">
            <ConfigProvider
              theme={{
                components: {
                  Tabs: {
                    itemColor: "#757575",
                    itemSelectedColor: "#EEEEEE",
                    itemHoverColor: "#B3B3B3",
                    inkBarColor: "#89C0F2",
                    titleFontSize: 14,
                  },
                },
              }}
            >
              <Tabs
                defaultActiveKey="1"
                items={filteredItems}
                onChange={onChange}
                className="generalTabs"
              />
            </ConfigProvider>
          </DrawerCard>
        </div>
      </div>

      {/* Footer - matching other drawers */}
      <div className="drawerFooter z-[5000] min-h-[4.1875rem] flex flex-col justify-start">
        <div
          style={{ justifyContent: "space-between" }}
          className="h-[4rem] pt-[.1rem] flex items-center px-[2.7rem]"
        >
          <div /> {/* Empty left side */}
          <button
            onClick={onClose}
            className="px-6 py-2 bg-[#89C0F2] text-white rounded-md hover:bg-[#6BA8E0] transition-colors text-sm font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ModelDetailDrawer;
