"use client";
import React, { useState, useEffect, useMemo } from "react";
import { Tabs, Tag, Image, ConfigProvider } from "antd";
import type { TabsProps } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { Drawer } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";
import ModelTags from "@/components/ui/ModelTags";
// Using custom text components with better theme support
interface TextComponentProps {
  children: React.ReactNode;
  className?: string;
  [key: string]: any;
}

const Text_12_400_757575: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-xs font-normal text-gray-500 dark:text-gray-400 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_12_400_B3B3B3: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-xs font-normal text-gray-600 dark:text-gray-300 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_12_400_EEEEEE: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-xs font-normal text-gray-800 dark:text-gray-200 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_12_600_EEEEEE: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-xs font-semibold text-gray-800 dark:text-gray-200 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_14_400_EEEEEE: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-sm font-normal text-gray-800 dark:text-gray-200 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_14_500_EEEEEE: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-sm font-medium text-gray-900 dark:text-gray-100 ${className}`}
    {...props}
  >
    {children}
  </div>
);

const Text_14_400_757575: React.FC<TextComponentProps> = ({
  children,
  className = "",
  ...props
}) => (
  <div
    className={`block text-sm font-normal text-gray-500 dark:text-gray-400 ${className}`}
    {...props}
  >
    {children}
  </div>
);
import dayjs from "dayjs";
import { Model } from "@/hooks/useModels";
import { successToast } from "@/components/toast";

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
  return (
    <Drawer
      open={visible}
      onClose={onClose}
      width={520}
      closable={false}
      className="bud-drawer"
      styles={{
        body: {
          padding: 0,
          overflow: "auto",
        },
      }}
    >
      {model && <ModelDetailContent model={model} onClose={onClose} />}
    </Drawer>
  );
};

const ModelDetailContent: React.FC<{ model: Model; onClose: () => void }> = ({
  model,
  onClose,
}) => {
  const [filteredItems, setFilteredItems] = useState<TabsProps["items"]>([]);
  const assetBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    successToast("Copied to clipboard");
  };

  const getModelIcon = (model: any) => {
    // Return an object that indicates whether it's a URL or an icon name
    if (model.icon) {
      // If icon exists, it's a URL
      const iconUrl = model.icon.startsWith("http")
        ? model.icon
        : `${assetBaseUrl}/${model.icon.startsWith("/") ? model.icon.slice(1) : model.icon}`;
      return { type: "url", value: iconUrl };
    }

    // Fallback to iconify icons
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

    // Default icon
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
        setIsOverflowing(element.scrollHeight > 50);
      }
    }, []);

    return (
      <div className="pt-[.25rem]">
        <div className="">
          {/* Description */}
          {model?.description ? (
            <>
              <div className="pt-[1.3rem]">
                <div
                  ref={descriptionRef}
                  className={`leading-[1.05rem] tracking-[.01em max-w-[100%] ${
                    isExpanded ? "" : "line-clamp-2"
                  } overflow-hidden`}
                  style={{
                    display: "-webkit-box",
                    WebkitBoxOrient: "vertical",
                  }}
                >
                  <Text_12_400_B3B3B3 className="leading-[180%]">
                    {model?.description}
                  </Text_12_400_B3B3B3>
                </div>
                {isOverflowing && (
                  <div className="flex justify-end">
                    <Text_12_600_EEEEEE
                      className="cursor-pointer leading-[1.05rem] tracking-[.01em] mt-[.3rem]"
                      onClick={toggleDescription}
                    >
                      {isExpanded ? "See less" : "See more"}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
              </div>
              <div className="hR mt-[1.1rem]"></div>
            </>
          ) : (
            <>
              <div className="flex justify-between items-center pt-[1.3rem]">
                <div>
                  <Text_14_400_EEEEEE>Description</Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Description not available
                  </Text_12_400_757575>
                </div>
              </div>
              <div className="hR mt-[1.5rem]"></div>
            </>
          )}

          {/* Basic Information */}
          <div className="pt-[1.3rem]">
            <Text_14_500_EEEEEE className="mb-4">
              Basic Information
            </Text_14_500_EEEEEE>
            <div className="bg-gray-100 dark:bg-white/5 rounded-lg p-4 space-y-3">
              <div className="flex justify-between">
                <Text_12_400_B3B3B3>Model Name</Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE>{model.name}</Text_12_400_EEEEEE>
              </div>
              <div className="flex justify-between">
                <Text_12_400_B3B3B3>Source</Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE>{model.source || "N/A"}</Text_12_400_EEEEEE>
              </div>
              <div className="flex justify-between">
                <Text_12_400_B3B3B3>Model Size</Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE>
                  {model.model_size ? `${model.model_size}B` : "N/A"}
                </Text_12_400_EEEEEE>
              </div>
              <div className="flex justify-between">
                <Text_12_400_B3B3B3>Provider Type</Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE>
                  {model.provider_type === "cloud_model" ? "Cloud" : "Local"}
                </Text_12_400_EEEEEE>
              </div>
              <div className="flex justify-between">
                <Text_12_400_B3B3B3>Created At</Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE>
                  {dayjs(model.created_at).format("DD MMM, YYYY")}
                </Text_12_400_EEEEEE>
              </div>
            </div>
          </div>
          <div className="hR mt-[1.5rem]"></div>

          {/* Modalities */}
          <div className="pt-[1.3rem]">
            <Text_14_400_EEEEEE>Modalities</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.33rem]">
              Following is the list of things model is really good at doing
            </Text_12_400_757575>
            <div className="modality flex items-center justify-start gap-[.5rem] mt-[1rem]">
              <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-gray-100 dark:bg-white/5 w-[50%] p-[1rem] rounded-[6px]">
                <Text_14_400_EEEEEE className="leading-[100%]">
                  Input
                </Text_14_400_EEEEEE>
                <div className="flex justify-center items-center gap-x-[.5rem]">
                  <div className="h-[1.25rem]">
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
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        model.modality.image.input
                          ? "/images/drawer/endpoints/image.png"
                          : "/images/drawer/endpoints/image-not.png"
                      }
                      alt={model.modality.image.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        model.modality.audio.input
                          ? "/images/drawer/endpoints/audio_speech.png"
                          : "/images/drawer/endpoints/audio_speech-not.png"
                      }
                      alt={model.modality.audio.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="leading-[100%]">
                  {[
                    model.modality.text.input && model.modality.text.label,
                    model.modality.image.input && model.modality.image.label,
                    model.modality.audio.input && model.modality.audio.label,
                  ]
                    .filter(Boolean)
                    .join(", ")}
                </Text_12_400_EEEEEE>
              </div>
              <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-gray-100 dark:bg-white/5 w-[50%] p-[1rem] rounded-[6px]">
                <Text_14_400_EEEEEE className="leading-[100%]">
                  Output
                </Text_14_400_EEEEEE>
                <div className="flex justify-center items-center gap-x-[.5rem]">
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        model.modality.text.output
                          ? "/images/drawer/endpoints/text.png"
                          : "/images/drawer/endpoints/text-not.png"
                      }
                      alt={model.modality.text.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        model.modality.image.output
                          ? "/images/drawer/endpoints/image.png"
                          : "/images/drawer/endpoints/image-not.png"
                      }
                      alt={model.modality.image.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        model.modality.audio.output
                          ? "/images/drawer/endpoints/audio_speech.png"
                          : "/images/drawer/endpoints/audio_speech-not.png"
                      }
                      alt={model.modality.audio.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="leading-[100%]">
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
          <div className="hR mt-[1.5rem]"></div>

          {/* Supported Endpoints */}
          <div className="pt-[1.3rem] pb-[1.4rem]">
            <Text_14_400_EEEEEE>Supported Endpoints</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.33rem]">
              Following is the list of things model is really good at doing
            </Text_12_400_757575>
            <div className="modality flex flex-wrap items-start justify-between gap-y-[.5rem] gap-x-[.75rem] mt-[1.5rem]">
              {Object.entries(model.supported_endpoints).map(([key, value]) => {
                const iconName = value.enabled
                  ? `${key}.png`
                  : `${key}-not.png`;
                return (
                  <div
                    key={key}
                    className="flex items-center justify-start gap-[.8rem] w-[calc(50%-0.4rem)] bg-gray-100 dark:bg-white/5 p-[1rem] rounded-[6px]"
                  >
                    <div className="h-[1.25rem]">
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
                    </div>
                    <div>
                      {value.enabled ? (
                        <>
                          <Text_14_400_EEEEEE>{value.label}</Text_14_400_EEEEEE>
                          <Text_12_400_B3B3B3 className="leading-[180%]">
                            {value.path}
                          </Text_12_400_B3B3B3>
                        </>
                      ) : (
                        <>
                          <Text_14_400_757575>{value.label}</Text_14_400_757575>
                          <Text_12_400_757575 className="leading-[180%]">
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
            <>
              <div className="hR mt-[1.5rem]"></div>
              <div className="pt-[1.3rem]">
                <Text_14_500_EEEEEE className="mb-4">
                  Model URI
                </Text_14_500_EEEEEE>
                <div className="bg-gray-100 dark:bg-[#FFFFFF08] rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <Text_12_400_EEEEEE className="font-mono truncate flex-1 mr-2">
                      {model.uri}
                    </Text_12_400_EEEEEE>
                    <button
                      onClick={() => copyToClipboard(model.uri)}
                      className="text-bud-text-muted hover:text-bud-text-primary transition-colors"
                    >
                      <CopyOutlined />
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Tags */}
          {model.tags && model.tags.length > 0 && (
            <>
              <div className="hR mt-[1.5rem]"></div>
              <div className="pt-[1.3rem]">
                <Text_14_500_EEEEEE className="mb-4">Tags</Text_14_500_EEEEEE>
                <div className="flex flex-wrap gap-2">
                  {model.tags.map((tag, index) => (
                    <Tag
                      key={index}
                      className="bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600"
                    >
                      {tag.name}
                    </Tag>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Strengths */}
          {model?.strengths?.length > 0 && (
            <>
              <div className="hR mt-[1.5rem]"></div>
              <div className="pt-[1.5rem] mb-[1.4rem]">
                <div>
                  <Text_14_400_EEEEEE>Model is Great at</Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Following is the list of things model is really good at
                    doing
                  </Text_12_400_757575>
                </div>
                <ul className="custom-bullet-list mt-[.9rem]">
                  {model?.strengths?.map((item: any, index: number) => (
                    <li key={index}>
                      <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                        {item}
                      </Text_12_400_EEEEEE>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          {/* Limitations */}
          {model?.limitations?.length > 0 && (
            <>
              <div className="hR"></div>
              <div className="pt-[1.5rem] mb-[1.4rem]">
                <div>
                  <Text_14_400_EEEEEE>
                    Model is Not Good With
                  </Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Following is the list of things model is not great at
                  </Text_12_400_757575>
                </div>
                <ul className="custom-bullet-list mt-[.9rem]">
                  {model?.limitations?.map((item: any, index: number) => (
                    <li key={index}>
                      <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                        {item}
                      </Text_12_400_EEEEEE>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
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
    [model, GeneralTab],
  );

  useEffect(() => {
    // Filter tabs based on model type if needed
    // For now, show all tabs for all model types
    setFilteredItems(items);
  }, [model, items]);

  const onChange = () => {
    // Handle tab change if needed
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-[#0A0A0A]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={onClose}
          className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          ← Back
        </button>
        <button
          onClick={onClose}
          className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="flex items-start justify-between w-full p-[1.35rem]">
          <div className="flex items-start justify-start max-w-[100%]">
            <div className="mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-bud-purple/20 to-bud-purple/10 flex items-center justify-center">
                {(() => {
                  const iconData = getModelIcon(model);
                  return iconData.type === "url" ? (
                    <img
                      src={iconData.value}
                      alt={model.name}
                      className="w-6 h-6 object-contain"
                      onError={(e) => {
                        // Fallback to default icon on error
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : (
                    <Icon
                      icon={iconData.value}
                      className="text-bud-purple text-[1.5rem]"
                    />
                  );
                })()}
              </div>
            </div>
            <div>
              <Text_14_400_EEEEEE className="mb-[0.65rem] leading-[140%]">
                {model?.name}
              </Text_14_400_EEEEEE>
              <ModelTags model={model} maxTags={3} limit={true} />
            </div>
          </div>
          <div className="flex justify-end items-start">
            {/* Action buttons can be added here if needed */}
          </div>
        </div>

        {/* Tabs */}
        <div className="px-[1.4rem]">
          <ConfigProvider
            theme={{
              token: {
                /* here is your global tokens */
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
        </div>
      </div>
    </div>
  );
};

export default ModelDetailDrawer;
