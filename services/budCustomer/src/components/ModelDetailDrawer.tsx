"use client";
import React, { useState, useEffect, useMemo } from "react";
import { Tabs, Tag, Image, ConfigProvider, Drawer, Form } from "antd";
import type { TabsProps } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import ModelTags from "@/components/ui/ModelTags";
import dayjs from "dayjs";
import { Model } from "@/hooks/useModels";
import { successToast } from "@/components/toast";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_14_400_757575,
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
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [submittable, setSubmittable] = useState(false);
  const [values, setValues] = useState({});

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
        {model && (
          <BudFormContext.Provider
            value={{
              form,
              submittable,
              loading,
              setLoading,
              values,
              isExpandedView: false,
              isExpandedViewOpen: false,
            }}
          >
            <ModelDetailContent model={model} onClose={onClose} />
          </BudFormContext.Provider>
        )}
      </div>
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
    }, []);

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
    [GeneralTab],
  );

  useEffect(() => {
    setFilteredItems(items);
  }, [model, items]);

  const onChange = () => {
    // Handle tab change if needed
  };

  return (
    <BudForm
      data={{}}
      onNext={() => {
        onClose();
      }}
      nextText="Close"
      showBack={false}
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Model Details"
            description={`View detailed information about ${model?.name || 'this model'}`}
          />
          <DrawerCard classNames="pb-0">
            {/* Model Header with Icon and Tags */}
            <div className="flex items-start justify-start gap-4 mb-6">
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
                <Text_14_400_EEEEEE className="mb-2 font-medium">
                  {model?.name}
                </Text_14_400_EEEEEE>
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

            {/* Tabs */}
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
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default ModelDetailDrawer;
