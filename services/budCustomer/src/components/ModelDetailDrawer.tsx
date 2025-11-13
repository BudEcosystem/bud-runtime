"use client";
import React, { useState, useEffect, useMemo } from "react";
import { Tabs, Tag, Image, ConfigProvider, Drawer, Form } from "antd";
import type { TabsProps } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import { ChevronDown } from "lucide-react";
import ModelTags from "@/components/ui/ModelTags";
import dayjs from "dayjs";
import { Model } from "@/hooks/useModels";
import { successToast, errorToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerBreadCrumbNavigation from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import CustomDropDown from "@/flows/components/CustomDropDown";
import CustomPopover from "@/flows/components/customPopover";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_14_400_757575,
  Text_20_400_FFFFFF,
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

export const ModelDetailContent: React.FC<{
  model: Model;
  onClose: () => void;
}> = ({ model, onClose }) => {
  const [filteredItems, setFilteredItems] = useState<TabsProps["items"]>([]);
  const assetBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;

  const handleCopyToClipboard = async (text: string) => {
    await copyToClipboard(text, {
      onSuccess: () => successToast("Copied to clipboard"),
      onError: () => errorToast("Failed to copy to clipboard"),
    });
  };

  const getModelIcon = (model: any) => {
    if (model.icon) {
      const iconUrl = model.icon.startsWith("http")
        ? model.icon
        : `${assetBaseUrl}/${model.icon.startsWith("/") ? model.icon.slice(1) : model.icon}`;
      return { type: "url", value: iconUrl };
    }

    const name = model.endpoint_name?.toLowerCase() || "";
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
              className={`${isExpanded ? "" : "line-clamp-3"} overflow-hidden`}
            >
              <Text_12_400_B3B3B3 className="leading-[180%] text-gray-800 dark:text-[#B3B3B3]">
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
          <Text_14_500_EEEEEE className="mb-3 text-gray-900 dark:text-[#EEEEEE]">
            Basic Information
          </Text_14_500_EEEEEE>
          <div className="bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3 className="text-gray-700 dark:text-[#B3B3B3]">
                Model Name
              </Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right text-gray-900 dark:text-[#EEEEEE]">
                {model.endpoint_name}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3 className="text-gray-700 dark:text-[#B3B3B3]">
                Source
              </Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right text-gray-900 dark:text-[#EEEEEE]">
                {model.source || "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3 className="text-gray-700 dark:text-[#B3B3B3]">
                Model Size
              </Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right text-gray-900 dark:text-[#EEEEEE]">
                {model.model_size ? `${model.model_size}B` : "N/A"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex justify-between items-center">
              <Text_12_400_B3B3B3 className="text-gray-700 dark:text-[#B3B3B3]">
                Provider Type
              </Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE className="text-right text-gray-900 dark:text-[#EEEEEE]">
                {model.provider_type === "cloud_model" ? "Cloud" : "Local"}
              </Text_12_400_EEEEEE>
            </div>
          </div>
        </div>

        {/* Modalities */}
        <div>
          <Text_14_500_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
            Modalities
          </Text_14_500_EEEEEE>
          <Text_12_400_757575 className="mt-1 mb-3 text-gray-600 dark:text-[#757575]">
            Input and output capabilities of the model
          </Text_12_400_757575>
          <div className="flex gap-3">
            <div className="flex flex-col items-center gap-3 bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] w-[50%] p-4 rounded-lg">
              <Text_14_400_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
                Input
              </Text_14_400_EEEEEE>
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
              <Text_12_400_EEEEEE className="text-center text-gray-900 dark:text-[#EEEEEE]">
                {[
                  model.modality.text.input && model.modality.text.label,
                  model.modality.image.input && model.modality.image.label,
                  model.modality.audio.input && model.modality.audio.label,
                ]
                  .filter(Boolean)
                  .join(", ")}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex flex-col items-center gap-3 bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] w-[50%] p-4 rounded-lg">
              <Text_14_400_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
                Output
              </Text_14_400_EEEEEE>
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
              <Text_12_400_EEEEEE className="text-center text-gray-900 dark:text-[#EEEEEE]">
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
          <Text_14_500_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
            Supported Endpoints
          </Text_14_500_EEEEEE>
          <Text_12_400_757575 className="mt-1 mb-3 text-gray-600 dark:text-[#757575]">
            Available API endpoints for this model
          </Text_12_400_757575>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(model.supported_endpoints).map(([key, value]) => {
              const iconName = value.enabled ? `${key}.png` : `${key}-not.png`;
              return (
                <div
                  key={key}
                  className="flex items-center gap-3 bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] p-3 rounded-lg"
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
                        <Text_14_400_EEEEEE className="truncate text-gray-900 dark:text-[#EEEEEE]">
                          {value.label}
                        </Text_14_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="truncate text-gray-700 dark:text-[#B3B3B3]">
                          {value.path}
                        </Text_12_400_B3B3B3>
                      </>
                    ) : (
                      <>
                        <Text_14_400_757575 className="truncate text-gray-700 dark:text-[#757575]">
                          {value.label}
                        </Text_14_400_757575>
                        <Text_12_400_757575 className="truncate text-gray-600 dark:text-[#757575]">
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
            <Text_14_500_EEEEEE className="mb-3 text-gray-900 dark:text-[#EEEEEE]">
              Model URI
            </Text_14_500_EEEEEE>
            <div className="bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] rounded-lg p-4">
              <div className="flex items-center justify-between gap-3">
                <Text_12_400_EEEEEE className="font-mono truncate flex-1 text-gray-900 dark:text-[#EEEEEE]">
                  {model.uri}
                </Text_12_400_EEEEEE>
                <button
                  onClick={() => handleCopyToClipboard(model.uri)}
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
            <Text_14_500_EEEEEE className="mb-3 text-gray-900 dark:text-[#EEEEEE]">
              Tags
            </Text_14_500_EEEEEE>
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
            <Text_14_500_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
              Model is Great at
            </Text_14_500_EEEEEE>
            <Text_12_400_757575 className="mt-1 mb-3 text-gray-600 dark:text-[#757575]">
              Key strengths and capabilities
            </Text_12_400_757575>
            <div className="bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] rounded-lg p-4">
              <ul className="space-y-2">
                {model?.strengths?.map((item: any, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-[#89C0F2] mt-1">•</span>
                    <Text_12_400_EEEEEE className="leading-relaxed text-gray-900 dark:text-[#EEEEEE]">
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
            <Text_14_500_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
              Model is Not Good With
            </Text_14_500_EEEEEE>
            <Text_12_400_757575 className="mt-1 mb-3 text-gray-600 dark:text-[#757575]">
              Known limitations and constraints
            </Text_12_400_757575>
            <div className="bg-gray-50 dark:bg-[rgba(255,255,255,0.027)] backdrop-blur-[10px] border border-gray-200 dark:border-[#1F1F1F] rounded-lg p-4">
              <ul className="space-y-2">
                {model?.limitations?.map((item: any, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-[#757575] mt-1">•</span>
                    <Text_12_400_EEEEEE className="leading-relaxed text-gray-900 dark:text-[#EEEEEE]">
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

  const UseThisModel = () => {
    type CodeType = "curl" | "python" | "javascript";
    const [selectedCode, setSelectedCode] = useState<CodeType>("curl");
    const [copyText, setCopyText] = useState<string>("Copy");

    // Function to get the appropriate endpoint and payload based on model type
    const getEndpointConfig = useMemo(() => {
      const modelName = model?.endpoint_name || "model";

      // Default to chat endpoint
      let endpoint = "/v1/chat/completions";
      let payloadExample: any = {
        model: modelName,
        max_tokens: 256,
        messages: [{ role: "user", content: "Summarize the given text" }],
      };

      // Check model supported endpoints
      if (model?.supported_endpoints) {
        // Check for embedding endpoint
        if (model.supported_endpoints.embedding?.enabled) {
          endpoint =
            model.supported_endpoints.embedding.path || "/v1/embeddings";
          payloadExample = {
            model: modelName,
            input: "Your text to embed",
          };
        }
        // Check for audio transcription endpoint
        else if (model.supported_endpoints.audio_transcription?.enabled) {
          endpoint =
            model.supported_endpoints.audio_transcription.path ||
            "/v1/audio/transcriptions";
          payloadExample = {
            model: modelName,
            file: "@/path/to/audio.mp3",
            response_format: "json",
          };
        }
        // Check for text-to-speech endpoint
        else if (model.supported_endpoints.audio_speech?.enabled) {
          endpoint =
            model.supported_endpoints.audio_speech.path || "/v1/audio/speech";
          payloadExample = {
            model: modelName,
            input: "Text to convert to speech",
            voice: "alloy",
          };
        }
        // Check for image generation endpoint
        else if (model.supported_endpoints.image_generation?.enabled) {
          endpoint =
            model.supported_endpoints.image_generation.path ||
            "/v1/images/generations";
          payloadExample = {
            model: modelName,
            prompt: "A cute baby sea otter",
            n: 1,
            size: "1024x1024",
          };
        }
        // Check for completion endpoint
        else if (model.supported_endpoints.completion?.enabled) {
          endpoint =
            model.supported_endpoints.completion.path || "/v1/completions";
          payloadExample = {
            model: modelName,
            prompt: "Once upon a time",
            max_tokens: 256,
          };
        }
        // Default to chat if it's enabled
        else if (model.supported_endpoints.chat?.enabled) {
          endpoint =
            model.supported_endpoints.chat.path || "/v1/chat/completions";
        }
      }

      return { endpoint, payloadExample };
    }, []);

    const { endpoint, payloadExample } = getEndpointConfig;
    const baseUrl =
      process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL ||
      "https://api.example.com";
    const apiUrl = `${baseUrl.replace( /\/+$/, '')}/${endpoint}`;
    console.log("baseUrl:", baseUrl);
    console.log("endpoint:", endpoint);
    console.log("API URL:", apiUrl);
    const generateCurlCommand = useMemo(() => {
      // Special handling for audio transcription (file upload)
      if (endpoint.includes("audio/transcriptions")) {
        return `curl --location '${apiUrl}' \\
  --header 'Authorization: Bearer {API_KEY_HERE}' \\
  --form 'file=@"/path/to/audio.mp3"' \\
  --form 'model="${payloadExample.model}"' \\
  --form 'response_format="json"'`;
      }

      // Standard JSON payload
      return `curl --location '${apiUrl}' \\
  --header 'Authorization: Bearer {API_KEY_HERE}' \\
  --header 'Content-Type: application/json' \\
  --data '${JSON.stringify(payloadExample, null, 2)}'`;
    }, [apiUrl, endpoint, payloadExample]);

    const generatePythonCode = useMemo(() => {
      // Special handling for audio transcription (file upload)
      if (endpoint.includes("audio/transcriptions")) {
        return `import requests

url = "${apiUrl}"
files = {'file': open('/path/to/audio.mp3', 'rb')}
data = {
  'model': '${payloadExample.model}',
  'response_format': 'json'
}
headers = {
  'Authorization': 'Bearer {API_KEY_HERE}'
}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.text)`;
      }

      // Standard JSON payload
      return `import requests
import json

url = "${apiUrl}"
payload = json.dumps(${JSON.stringify(payloadExample, null, 2)})
headers = {
  'Authorization': 'Bearer {API_KEY_HERE}',
  'Content-Type': 'application/json'
}

response = requests.post(url, headers=headers, data=payload)
print(response.text)`;
    }, [apiUrl, endpoint, payloadExample]);

    const generateJavaScriptCode = useMemo(() => {
      // Special handling for audio transcription (file upload)
      if (endpoint.includes("audio/transcriptions")) {
        return `const formData = new FormData();
formData.append('file', fileInput.files[0]); // fileInput is your file input element
formData.append('model', '${payloadExample.model}');
formData.append('response_format', 'json');

fetch('${apiUrl}', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer {API_KEY_HERE}'
  },
  body: formData
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));`;
      }

      // Standard JSON payload
      return `const data = ${JSON.stringify(payloadExample, null, 2)};

fetch('${apiUrl}', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer {API_KEY_HERE}',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));`;
    }, [apiUrl, endpoint, payloadExample]);

    const codeSnippets = useMemo(
      () => ({
        curl: generateCurlCommand,
        python: generatePythonCode,
        javascript: generateJavaScriptCode,
      }),
      [generateCurlCommand, generatePythonCode, generateJavaScriptCode],
    );
    const [selectedText, setSelectedText] = useState<string>(
      codeSnippets[selectedCode],
    );

    // Update selected text when code type or snippets change
    useEffect(() => {
      setSelectedText(codeSnippets[selectedCode]);
    }, [selectedCode, codeSnippets]);
    const selectType = (type: CodeType) => {
      setSelectedCode(type);
      setSelectedText(codeSnippets[type]);
    };

    const handleCopy = async (text: string) => {
      await copyToClipboard(text, {
        onSuccess: () => {
          setCopyText("Copied!");
          setTimeout(() => {
            setCopyText("Copy");
          }, 2000);
        },
        onError: () => {
          setCopyText("Failed to copy");
          errorToast("Failed to copy to clipboard");
        },
      });
    };

    return (
      <div className="space-y-6">
        <div>
          <Text_20_400_FFFFFF className="tracking-[.03rem] text-gray-900 dark:text-[#FFFFFF]">
            Code Snippet
          </Text_20_400_FFFFFF>
          <Text_12_400_757575 className="tracking-[.004rem] mt-[1rem] text-gray-600 dark:text-[#757575]">
            Copy the code below and use it for deployment
          </Text_12_400_757575>
        </div>

        <div className="flex justify-start">
          <CustomDropDown
            parentClassNames="cursor-pointer"
            Placement="bottomLeft"
            buttonContent={
              <div className="cursor-pointer border border-[.5px] border-[#965CDE] rounded-[6px] bg-[#1E0C34] min-w-[4rem] min-h-[1.75rem] flex items-center justify-center px-[.6rem]">
                <Text_12_600_EEEEEE className="cursor-pointer flex items-center justify-center text-white dark:text-[#EEEEEE]">
                  {selectedCode.charAt(0).toUpperCase() + selectedCode.slice(1)}
                </Text_12_600_EEEEEE>
                <ChevronDown className="w-[1rem] text-[#EEEEEE] text-[.75rem] ml-[.15rem]" />
              </div>
            }
            items={[
              {
                key: "1",
                label: "Curl",
                onClick: () => selectType("curl"),
              },
              {
                key: "2",
                label: "Python",
                onClick: () => selectType("python"),
              },
              {
                key: "3",
                label: "JavaScript",
                onClick: () => selectType("javascript"),
              },
            ]}
          />
        </div>

        <div className="custom-code rounded-[8px] relative bg-[#FFFFFF08] w-full overflow-hidden">
          <CustomPopover title={copyText} contentClassNames="py-[.3rem]">
            <div
              className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center absolute right-[0.35rem] top-[0.65rem] cursor-pointer hover:bg-[#1F1F1F] z-10"
              onClick={() => handleCopy(selectedText)}
            >
              <Image
                preview={false}
                src="/images/drawer/Copy.png"
                alt="copy"
                style={{ height: ".75rem" }}
              />
            </div>
          </CustomPopover>

          <div className="markdown-body">
            <SyntaxHighlighter
              language={
                selectedCode === "python"
                  ? "python"
                  : selectedCode === "javascript"
                    ? "javascript"
                    : "bash"
              }
              style={oneDark}
              showLineNumbers
              customStyle={{
                margin: 0,
                borderRadius: "8px",
                fontSize: "0.75rem",
              }}
            >
              {selectedText}
            </SyntaxHighlighter>
          </div>
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
      {
        key: "2",
        label: "Use Model",
        children: <UseThisModel />,
      },
    ],
    [], // Remove dependencies as they're component functions defined in the same render
  );

  useEffect(() => {
    setFilteredItems(items);
  }, [items]);

  const onChange = () => {
    // Handle tab change if needed
  };

  return (
    <BudForm
      data={{
        name: "Model details",
        description: "",
        tags: [],
        icon: "",
      }}
      onNext={() => {
        onClose();
      }}
      nextText="Close"
      showBack={false}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Model Details"
            description={`View detailed information about ${model?.endpoint_name || "this model"}`}
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
                        alt={model.endpoint_name}
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
                <Text_14_400_EEEEEE className="mb-2 font-medium text-gray-900 dark:text-[#EEEEEE]">
                  {model?.endpoint_name}
                </Text_14_400_EEEEEE>
                <ModelTags
                  model={{
                    ...model,
                    endpoints_count: model.supported_endpoints
                      ? Object.values(model.supported_endpoints).filter(
                          (e: any) => e.enabled,
                        ).length
                      : model.endpoints_count,
                  }}
                  maxTags={3}
                  limit={true}
                />
                <div className="flex items-center gap-2 mt-2">
                  <Icon
                    icon="ph:calendar"
                    className="text-[#757575] text-[0.875rem]"
                  />
                  <Text_12_400_B3B3B3 className="text-gray-700 dark:text-[#B3B3B3]">
                    Created on&nbsp;&nbsp;
                  </Text_12_400_B3B3B3>
                  <Text_12_400_EEEEEE className="text-gray-900 dark:text-[#EEEEEE]">
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
                className="generalTabs [&_.ant-tabs-tab]:text-gray-500 [&_.ant-tabs-tab]:dark:text-[#757575] [&_.ant-tabs-tab-active_.ant-tabs-tab-btn]:!text-black [&_.ant-tabs-tab-active_.ant-tabs-tab-btn]:dark:!text-[#EEEEEE] [&_.ant-tabs-tab:hover]:text-gray-700 [&_.ant-tabs-tab:hover]:dark:text-[#B3B3B3]"
              />
            </ConfigProvider>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default ModelDetailDrawer;
