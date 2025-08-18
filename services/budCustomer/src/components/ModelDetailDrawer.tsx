"use client";
import React from "react";
import {
  Drawer,
  Tabs,
  Tag,
  Divider,
  Space,
  Button,
  Badge,
  Tooltip,
  Image,
} from "antd";
import { CloseOutlined, CopyOutlined, LinkOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import {
  Text_10_400_B3B3B3,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_13_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_600_FFFFFF,
  Text_14_400_757575,
} from "@/components/ui/text";
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
  if (!model) return null;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    successToast("Copied to clipboard");
  };

  const assetBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;

  const getModelIcon = (
    model: Model,
  ): { type: "url" | "icon"; value: string } => {
    // Check if model has an icon property and it's not empty
    if (model?.icon && model.icon.trim() !== "") {
      // If icon starts with http/https, use it directly
      if (
        model.icon.startsWith("http://") ||
        model.icon.startsWith("https://")
      ) {
        return { type: "url", value: model.icon };
      }
      // If icon starts with /, remove it to avoid double slashes
      const iconPath = model.icon.startsWith("/")
        ? model.icon.slice(1)
        : model.icon;
      const fullIconUrl = `${assetBaseUrl}/${iconPath}`;
      return { type: "url", value: fullIconUrl };
    }

    // Fallback to iconify icons based on model name
    const modelName = model?.name?.toLowerCase() || "";
    if (modelName.includes("gpt"))
      return { type: "icon", value: "simple-icons:openai" };
    if (modelName.includes("claude"))
      return { type: "icon", value: "simple-icons:anthropic" };
    if (modelName.includes("llama"))
      return { type: "icon", value: "simple-icons:meta" };
    if (modelName.includes("dall")) return { type: "icon", value: "ph:image" };
    if (modelName.includes("whisper"))
      return { type: "icon", value: "ph:microphone" };
    if (modelName.includes("stable"))
      return { type: "icon", value: "ph:palette" };
    return { type: "icon", value: "ph:cube" };
  };

  const GeneralTab = () => (
    <div className="space-y-6">
      {/* Basic Information */}
      <div>
        <Text_14_500_EEEEEE className="mb-4">
          Basic Information
        </Text_14_500_EEEEEE>
        <div className="bg-bud-bg-secondary rounded-lg p-4 space-y-3">
          <div className="flex justify-between">
            <Text_12_400_B3B3B3>Model Name</Text_12_400_B3B3B3>
            <Text_12_400_EEEEEE>{model.name}</Text_12_400_EEEEEE>
          </div>
          <div className="flex justify-between">
            <Text_12_400_B3B3B3>Author</Text_12_400_B3B3B3>
            <Text_12_400_EEEEEE>{model.author || "Unknown"}</Text_12_400_EEEEEE>
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

      {/* Description */}
      {model.description && (
        <div>
          <Text_14_500_EEEEEE className="mb-4">Description</Text_14_500_EEEEEE>
          <div className="bg-bud-bg-secondary rounded-lg p-4">
            <Text_12_400_EEEEEE className="leading-relaxed whitespace-pre-wrap">
              {model.description}
            </Text_12_400_EEEEEE>
          </div>
        </div>
      )}

      {/* Model URI */}
      {model.uri && (
        <div>
          <Text_14_500_EEEEEE className="mb-4">Model URI</Text_14_500_EEEEEE>
          <div className="bg-bud-bg-secondary rounded-lg p-4">
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
      )}

      {/* Tasks */}
      {model.tasks && model.tasks.length > 0 && (
        <div>
          <Text_14_500_EEEEEE className="mb-4">Tasks</Text_14_500_EEEEEE>
          <div className="flex flex-wrap gap-2">
            {model.tasks.map((task, index) => (
              <Tag
                key={index}
                style={{
                  backgroundColor: task.color || "#1F1F1F",
                  border: "1px solid #2F2F2F",
                  color: "#EEEEEE",
                }}
              >
                {task.name}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {/* Tags */}
      {model.tags && model.tags.length > 0 && (
        <div>
          <Text_14_500_EEEEEE className="mb-4">Tags</Text_14_500_EEEEEE>
          <div className="flex flex-wrap gap-2">
            {model.tags.map((tag, index) => (
              <Tag
                key={index}
                style={{
                  backgroundColor: tag.color || "#1F1F1F",
                  border: "1px solid #2F2F2F",
                  color: "#EEEEEE",
                }}
              >
                {tag.name}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {model?.strengths?.length > 0 && (
        <>
          <div className="pt-[1.5rem] mb-[1.4rem]">
            <div>
              <Text_14_400_EEEEEE>Model is Great at</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="pt-[.45rem]">
                Following is the list of things model is really good at doing
              </Text_12_400_757575>
            </div>
            <ul className="custom-bullet-list mt-[.9rem]">
              {model?.strengths?.map(
                (
                  item:
                    | string
                    | number
                    | bigint
                    | boolean
                    | React.ReactElement<
                        unknown,
                        string | React.JSXElementConstructor<any>
                      >
                    | Iterable<React.ReactNode>
                    | React.ReactPortal
                    | Promise<
                        | string
                        | number
                        | bigint
                        | boolean
                        | React.ReactPortal
                        | React.ReactElement<
                            unknown,
                            string | React.JSXElementConstructor<any>
                          >
                        | Iterable<React.ReactNode>
                        | null
                        | undefined
                      >
                    | null
                    | undefined,
                  index: any,
                ) => (
                  <li key={`strength-${index}`}>
                    <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                      {item}
                    </Text_12_400_EEEEEE>
                  </li>
                ),
              )}
            </ul>
          </div>
          <div className="hR"></div>
        </>
      )}
      {model?.limitations?.length > 0 && (
        <>
          <div className="pt-[1.5rem] mb-[1.4rem]">
            <div>
              <Text_14_400_EEEEEE>Model is Not Good With</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="pt-[.45rem]">
                Following is the list of things model is not great at
              </Text_12_400_757575>
            </div>
            <ul className="custom-bullet-list mt-[.9rem]">
              {model?.limitations?.map(
                (
                  item:
                    | string
                    | number
                    | bigint
                    | boolean
                    | React.ReactElement<
                        unknown,
                        string | React.JSXElementConstructor<any>
                      >
                    | Iterable<React.ReactNode>
                    | React.ReactPortal
                    | Promise<
                        | string
                        | number
                        | bigint
                        | boolean
                        | React.ReactPortal
                        | React.ReactElement<
                            unknown,
                            string | React.JSXElementConstructor<any>
                          >
                        | Iterable<React.ReactNode>
                        | null
                        | undefined
                      >
                    | null
                    | undefined,
                  index: any,
                ) => (
                  <li key={`limitation-${index}`}>
                    <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                      {item}
                    </Text_12_400_EEEEEE>
                  </li>
                ),
              )}
            </ul>
          </div>
          <div className="hR"></div>
        </>
      )}
    </div>
  );

  const ModalityTab = () => (
    <div className="space-y-6">
      <div>
        <Text_14_400_EEEEEE>Model is Great at</Text_14_400_EEEEEE>
        <Text_12_400_757575 className="pt-[.45rem]">
          Following is the list of things model is really good at doing
        </Text_12_400_757575>
      </div>
      <div className="bg-bud-bg-secondary rounded-lg p-4">
        <div className="modality flex items-center justify-start gap-[.5rem] ">
          <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-[#ffffff08] w-[50%] p-[1rem] rounded-[6px]">
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
          <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-[#ffffff08] w-[50%] p-[1rem] rounded-[6px]">
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

      {/* Supported Endpoints */}
      <div className="space-y-6">
        <div>
          <Text_14_400_EEEEEE>Supported Endpoints</Text_14_400_EEEEEE>
          <Text_12_400_757575 className="pt-[.45rem]">
            Following is the list of things model is really good at doing
          </Text_12_400_757575>
        </div>
        <div className="bg-bud-bg-secondary rounded-lg p-4">
          <div className="modality flex flex-wrap items-start justify-between gap-y-[.5rem] gap-x-[.75rem] ">
            {Object.entries(model.supported_endpoints).map(([key, value]) => {
              const iconName = value.enabled ? `${key}.png` : `${key}-not.png`;
              return (
                <div
                  key={key}
                  className="flex items-center justify-start gap-[.8rem] w-[calc(50%-0.4rem)] bg-[#ffffff08] p-[1rem] rounded-[6px]"
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
      </div>
    </div>
  );

  const ArchitectureTab = () => (
    <div className="space-y-6">
      {/* Architecture Text Config */}
      {model.architecture_text_config && (
        <div>
          <Text_14_500_EEEEEE className="mb-4">
            Text Architecture
          </Text_14_500_EEEEEE>
          <div className="bg-bud-bg-secondary rounded-lg p-4 space-y-3">
            <div className="flex justify-between">
              <Text_12_400_B3B3B3>Context Length</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {model.architecture_text_config.context_length?.toLocaleString() ||
                  "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between">
              <Text_12_400_B3B3B3>Hidden Size</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {model.architecture_text_config.hidden_size?.toLocaleString() ||
                  "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between">
              <Text_12_400_B3B3B3>Number of Layers</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {model.architecture_text_config.num_layers || "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between">
              <Text_12_400_B3B3B3>Attention Heads</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {model.architecture_text_config.num_attention_heads || "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between">
              <Text_12_400_B3B3B3>Vocab Size</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {model.architecture_text_config.vocab_size?.toLocaleString() ||
                  "N/A"}
              </Text_12_400_EEEEEE>
            </div>
          </div>
        </div>
      )}

      {/* External Links */}
      <div>
        <Text_14_500_EEEEEE className="mb-4">External Links</Text_14_500_EEEEEE>
        <div className="space-y-2">
          {model.github_url && (
            <a
              href={model.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-bud-bg-secondary rounded-lg p-3 hover:bg-bud-bg-tertiary transition-colors"
            >
              <Icon icon="mdi:github" className="text-xl" />
              <Text_12_400_EEEEEE>GitHub Repository</Text_12_400_EEEEEE>
              <LinkOutlined className="ml-auto text-bud-text-muted" />
            </a>
          )}
          {model.huggingface_url && (
            <a
              href={model.huggingface_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-bud-bg-secondary rounded-lg p-3 hover:bg-bud-bg-tertiary transition-colors"
            >
              <Icon icon="simple-icons:huggingface" className="text-xl" />
              <Text_12_400_EEEEEE>Hugging Face</Text_12_400_EEEEEE>
              <LinkOutlined className="ml-auto text-bud-text-muted" />
            </a>
          )}
          {model.website_url && (
            <a
              href={model.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-bud-bg-secondary rounded-lg p-3 hover:bg-bud-bg-tertiary transition-colors"
            >
              <Icon icon="ph:globe" className="text-xl" />
              <Text_12_400_EEEEEE>Website</Text_12_400_EEEEEE>
              <LinkOutlined className="ml-auto text-bud-text-muted" />
            </a>
          )}
        </div>
      </div>

      {/* Verification Status */}
      <div>
        <Text_14_500_EEEEEE className="mb-4">
          Verification Status
        </Text_14_500_EEEEEE>
        <div className="bg-bud-bg-secondary rounded-lg p-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Text_12_400_B3B3B3>Bud Verified</Text_12_400_B3B3B3>
              <Badge
                status={model.bud_verified ? "success" : "default"}
                text={model.bud_verified ? "Verified" : "Not Verified"}
              />
            </div>
            <div className="flex items-center justify-between">
              <Text_12_400_B3B3B3>Security Scan</Text_12_400_B3B3B3>
              <Badge
                status={model.scan_verified ? "success" : "default"}
                text={model.scan_verified ? "Passed" : "Not Scanned"}
              />
            </div>
            <div className="flex items-center justify-between">
              <Text_12_400_B3B3B3>Evaluation</Text_12_400_B3B3B3>
              <Badge
                status={model.eval_verified ? "success" : "default"}
                text={model.eval_verified ? "Evaluated" : "Not Evaluated"}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const tabItems = [
    {
      key: "general",
      label: "General",
      children: <GeneralTab />,
    },
    {
      key: "modality",
      label: "Modality & Endpoints",
      children: <ModalityTab />,
    },
    // {
    //   key: "architecture",
    //   label: "Architecture",
    //   children: <ArchitectureTab />,
    // },
  ];

  return (
    <Drawer
      title={
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-bud-purple/20 to-bud-purple/10 flex items-center justify-center">
            {(() => {
              const iconData = getModelIcon(model);
              if (iconData.type === "url") {
                return (
                  <img
                    src={iconData.value}
                    alt={model.name}
                    className="w-6 h-6 object-contain"
                    onError={(e) => {
                      // Fallback to placeholder if image fails to load
                      e.currentTarget.src =
                        'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"%3E%3Cpath fill="%239b59b6" d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/%3E%3C/svg%3E';
                    }}
                  />
                );
              } else {
                return (
                  <Icon
                    icon={iconData.value}
                    className="text-bud-purple text-[1.5rem]"
                  />
                );
              }
            })()}
          </div>
          <div>
            <Text_16_600_FFFFFF>{model.name}</Text_16_600_FFFFFF>
            <Text_12_400_B3B3B3 className="mt-1">
              {model.provider_type === "cloud_model"
                ? "Cloud Model"
                : "Local Model"}
            </Text_12_400_B3B3B3>
          </div>
        </div>
      }
      placement="right"
      width={600}
      open={visible}
      onClose={onClose}
      closeIcon={
        <CloseOutlined className="text-bud-text-muted hover:text-bud-text-primary" />
      }
      className="model-detail-drawer"
      styles={{
        body: {
          backgroundColor: "#0F0F0F",
          padding: "24px",
        },
        header: {
          backgroundColor: "#0F0F0F",
          borderBottom: "1px solid #1F1F1F",
        },
      }}
    >
      <Tabs
        items={tabItems}
        className="model-detail-tabs"
        style={{
          color: "#EEEEEE",
        }}
      />
    </Drawer>
  );
};

export default ModelDetailDrawer;
