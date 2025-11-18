import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_20_400_FFFFFF,
} from "@/components/ui/text";
import { Image } from "antd";
import React, { useEffect, useMemo, useState } from "react";
import Tags from "../components/DrawerTags";
import CustomDropDown from "../components/CustomDropDown";
import { ChevronDown } from "lucide-react";
import { useEndPoints } from "src/hooks/useEndPoint";
import CustomPopover from "../components/customPopover";

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDrawer } from "src/hooks/useDrawer";
import { copyToClipboard } from "@/utils/clipboard";

type EndpointTemplate = {
  id: string;
  label: string;
  defaultPath: string;
  requiresFileUpload?: boolean;
  buildPayload: (modelName?: string) => Record<string, unknown>;
};

type EndpointConfig = {
  key: string;
  label: string;
  path: string;
  payload: Record<string, unknown>;
  requiresFileUpload?: boolean;
};

const ensureLeadingSlash = (path: string) => {
  if (!path) {
    return "";
  }

  return path.startsWith("/") ? path : `/${path}`;
};

const stripLeadingSlash = (path: string) =>
  path.startsWith("/") ? path.slice(1) : path;

const createLabelFromPath = (path: string) => {
  const cleanPath = stripLeadingSlash(path);

  if (!cleanPath) {
    return "Endpoint";
  }

  return cleanPath
    .split("/")
    .map((segment) =>
      segment
        .replace(/[_-]/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase())
    )
    .join(" / ");
};

const documentsTemplate: EndpointTemplate = {
  id: "documents",
  label: "Documents",
  defaultPath: "/v1/documents",
  buildPayload: (modelName = "MODEL_NAME") => ({
    model: modelName,
    document: {
      type: "document_url",
      document_url: "https://example.com/document.pdf",
    }
    // prompt: "Summarize the document and extract key facts",
  }),
};

const endpointTemplates: Record<string, EndpointTemplate> = {
  chat: {
    id: "chat",
    label: "Chat Completions",
    defaultPath: "/v1/chat/completions",
    buildPayload: (modelName = "MODEL_NAME") => ({
      model: modelName,
      max_tokens: 256,
      messages: [{ role: "user", content: "Summarize the given text" }],
    }),
  },
  completions: {
    id: "completions",
    label: "Completions",
    defaultPath: "/v1/completions",
    buildPayload: (modelName = "MODEL_NAME") => ({
      model: modelName,
      prompt: "Once upon a time",
      max_tokens: 256,
    }),
  },
  embedding: {
    id: "embedding",
    label: "Embeddings",
    defaultPath: "/v1/embeddings",
    buildPayload: (modelName = "MODEL_NAME") => ({
      model: modelName,
      input: "Your text to embed",
    }),
  },
  audio_transcription: {
    id: "audio_transcription",
    label: "Audio Transcriptions",
    defaultPath: "/v1/audio/transcriptions",
    requiresFileUpload: true,
    buildPayload: (modelName = "MODEL_NAME") => ({
      model: modelName,
      file: "@/path/to/audio.mp3",
      response_format: "json",
    }),
  },
  audio_speech: {
    id: "audio_speech",
    label: "Text To Speech",
    defaultPath: "/v1/audio/speech",
    buildPayload: (modelName = "MODEL_NAME") => ({
      model: modelName,
      input: "Text to convert to speech",
      voice: "alloy",
    }),
  },
  image_generation: {
    id: "image_generation",
    label: "Image Generations",
    defaultPath: "/v1/images/generations",
    buildPayload: (modelName = "MODEL_NAME") => ({
      model: modelName,
      prompt: "A cute baby sea otter",
      n: 1,
      size: "1024x1024",
    }),
  },
  documents: documentsTemplate,
  document: documentsTemplate,
};

const templateList = Array.from(new Set(Object.values(endpointTemplates)));

const getTemplateByPath = (path: string) => {
  const normalized = ensureLeadingSlash(path);

  return templateList.find(
    (template) => ensureLeadingSlash(template.defaultPath) === normalized
  );
};

const joinBaseWithPath = (base: string, path: string) => {
  if (!base) {
    return stripLeadingSlash(path);
  }

  const normalizedBase = base.endsWith("/") ? base : `${base}/`;
  const normalizedPath = stripLeadingSlash(path);

  return `${normalizedBase}${normalizedPath}`;
};

const generateCurlCommand = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) {
    return "";
  }

  if (config.requiresFileUpload || config.path.includes("audio/transcriptions")) {
    const payload = config.payload;
    const fileValue = payload.file;
    const filePath =
      typeof fileValue === "string"
        ? fileValue.replace(/^@/, "")
        : "/path/to/audio.mp3";
    const restEntries = Object.entries(payload).filter(
      ([key]) => key !== "file"
    );
    const restLines = restEntries
      .map(([key, value], index) => {
        const formattedValue =
          value === undefined || value === null
            ? ""
            : typeof value === "string"
            ? value
            : JSON.stringify(value);
        const continuation = index === restEntries.length - 1 ? "" : " \\\n";

        return `  --form '${key}="${formattedValue}"'${continuation}`;
      })
      .join("");
    const restSection = restLines ? ` \\\n${restLines}` : "";

    return `curl --location '${apiUrl}' \\\n  --header 'Authorization: Bearer {API_KEY_HERE}' \\\n  --form 'file=@"${filePath}"'${restSection}`;
  }

  return `curl --location '${apiUrl}' \\\n  --header 'Authorization: Bearer {API_KEY_HERE}' \\\n  --header 'Content-Type: application/json' \\\n  --data '${JSON.stringify(config.payload, null, 2)}'`;
};

const generatePythonCode = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) {
    return "";
  }

  if (config.requiresFileUpload || config.path.includes("audio/transcriptions")) {
    const payload = config.payload;
    const fileValue = payload.file;
    const filePath =
      typeof fileValue === "string"
        ? fileValue.replace(/^@/, "")
        : "/path/to/audio.mp3";
    const formEntries = Object.entries(payload).filter(
      ([key]) => key !== "file"
    );
    const dataBlock = formEntries.length
      ? `{\n${formEntries
          .map(
            ([key, value]) => `  '${key}': ${JSON.stringify(value)}`
          )
          .join(",\n")}\n}`
      : "{}";

    return `import requests\n\nurl = "${apiUrl}"\nfiles = {'file': open('${filePath}', 'rb')}\ndata = ${dataBlock}\nheaders = {\n  'Authorization': 'Bearer {API_KEY_HERE}'\n}\n\nresponse = requests.post(url, headers=headers, files=files, data=data)\nprint(response.text)`;
  }

  return `import requests\nimport json\n\nurl = "${apiUrl}"\npayload = json.dumps(${JSON.stringify(
    config.payload,
    null,
    2
  )})\nheaders = {\n  'Authorization': 'Bearer {API_KEY_HERE}',\n  'Content-Type': 'application/json'\n}\n\nresponse = requests.post(url, headers=headers, data=payload)\nprint(response.text)`;
};

const generateJavaScriptCode = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) {
    return "";
  }

  if (config.requiresFileUpload || config.path.includes("audio/transcriptions")) {
    const payload = config.payload;
    const formEntries = Object.entries(payload).filter(
      ([key]) => key !== "file"
    );
    const additionalFormLines = formEntries
      .map(
        ([key, value]) =>
          `formData.append('${key}', ${JSON.stringify(value)});`
      )
      .join("\n");
    const additionalSection = additionalFormLines
      ? `${additionalFormLines}\n`
      : "";

    return `const formData = new FormData();\nformData.append('file', fileInput.files[0]); // fileInput is your file input element\n${additionalSection}\nfetch('${apiUrl}', {\n  method: 'POST',\n  headers: {\n    'Authorization': 'Bearer {API_KEY_HERE}'\n  },\n  body: formData\n})\n.then(response => response.json())\n.then(data => console.log(data))\n.catch(error => console.error('Error:', error));`;
  }

  return `const data = ${JSON.stringify(config.payload, null, 2)};\n\nfetch('${apiUrl}', {\n  method: 'POST',\n  headers: {\n    'Authorization': 'Bearer {API_KEY_HERE}',\n    'Content-Type': 'application/json'\n  },\n  body: JSON.stringify(data)\n})\n.then(response => response.json())\n.then(data => console.log(data))\n.catch(error => console.error('Error:', error));`;
};

export default function UseModel() {
  const { drawerProps } = useDrawer();
  const { clusterDetails } = useEndPoints();

  const tags = [
    {
      name:
        drawerProps?.endpoint?.name ||
        drawerProps?.name ||
        clusterDetails?.name,
      color: "#D1B854",
    },
    {
      name:
        drawerProps?.endpoint?.cluster?.name ||
        drawerProps?.name ||
        clusterDetails?.cluster?.name,
      color: "#D1B854",
    },
  ];

  const modelNameForPayload =
    drawerProps?.endpoint?.name ||
    drawerProps?.name ||
    clusterDetails?.name ||
    "MODEL_NAME";

  const endpointSupportedEndpoints = drawerProps?.endpoint?.supported_endpoints;
  const modelSupportedEndpoints =
    drawerProps?.endpoint?.model?.supported_endpoints ||
    clusterDetails?.model?.supported_endpoints;

  const endpointConfigs = useMemo<EndpointConfig[]>(() => {
    const configsMap = new Map<string, EndpointConfig>();

    const registerTemplate = (
      template: EndpointTemplate,
      overridePath?: string | null
    ) => {
      const targetPath = overridePath || template.defaultPath;
      const normalizedPath = ensureLeadingSlash(`${targetPath}`);

      if (!normalizedPath || configsMap.has(normalizedPath)) {
        return;
      }

      configsMap.set(normalizedPath, {
        key: normalizedPath,
        label: template.label,
        path: normalizedPath,
        payload: template.buildPayload(modelNameForPayload),
        requiresFileUpload: template.requiresFileUpload,
      });
    };

    const registerPath = (pathValue?: unknown) => {
      if (!pathValue) {
        return;
      }

      const normalizedPath = ensureLeadingSlash(`${pathValue}`);

      if (!normalizedPath || configsMap.has(normalizedPath)) {
        return;
      }

      const template = getTemplateByPath(normalizedPath);

      configsMap.set(normalizedPath, {
        key: normalizedPath,
        label: template?.label ?? createLabelFromPath(normalizedPath),
        path: normalizedPath,
        payload:
          template?.buildPayload(modelNameForPayload) ?? {
            model: modelNameForPayload,
          },
        requiresFileUpload: template?.requiresFileUpload,
      });
    };

    if (Array.isArray(endpointSupportedEndpoints)) {
      endpointSupportedEndpoints.forEach((pathValue) => {
        registerPath(pathValue);
      });
    }

    if (modelSupportedEndpoints && typeof modelSupportedEndpoints === "object") {
      Object.entries(modelSupportedEndpoints).forEach(([key, value]) => {
        if (!value) {
          return;
        }

        const template = endpointTemplates[key];

        if (
          typeof value === "object" &&
          value !== null &&
          ("path" in value || "enabled" in value)
        ) {
          const typedValue = value as { enabled?: boolean; path?: string | null };
          const isEnabled =
            typedValue.enabled === undefined ? true : Boolean(typedValue.enabled);

          if (!isEnabled) {
            return;
          }

          if (template) {
            registerTemplate(template, typedValue.path ?? undefined);
          } else if (typedValue.path) {
            registerPath(typedValue.path);
          }
        } else if (template) {
          registerTemplate(template);
        }
      });
    }

    if (!configsMap.size) {
      registerTemplate(endpointTemplates.chat);
    }

    return Array.from(configsMap.values());
  }, [
    endpointSupportedEndpoints,
    modelSupportedEndpoints,
    modelNameForPayload,
  ]);

  const [selectedEndpointKey, setSelectedEndpointKey] = useState<string>(
    endpointConfigs[0]?.key || ""
  );

  useEffect(() => {
    if (!endpointConfigs.length) {
      setSelectedEndpointKey("");
      return;
    }

    const hasCurrent = endpointConfigs.some(
      (config) => config.key === selectedEndpointKey
    );

    if (!hasCurrent) {
      setSelectedEndpointKey(endpointConfigs[0].key);
    }
  }, [endpointConfigs, selectedEndpointKey]);

  const selectedEndpoint = useMemo(
    () =>
      endpointConfigs.find((config) => config.key === selectedEndpointKey) ||
      endpointConfigs[0],
    [endpointConfigs, selectedEndpointKey]
  );

  const baseUrl =
    process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BASE_URL ||
    "";
  const apiUrl = selectedEndpoint
    ? joinBaseWithPath(baseUrl, selectedEndpoint.path)
    : baseUrl;

  const codeSnippets = useMemo(
    () => ({
      curl: generateCurlCommand(apiUrl, selectedEndpoint),
      python: generatePythonCode(apiUrl, selectedEndpoint),
      javascript: generateJavaScriptCode(apiUrl, selectedEndpoint),
    }),
    [apiUrl, selectedEndpoint]
  );

  const [selectedCode, setSelectedCode] = useState("curl");
  const [selectedText, setSelectedText] = useState(
    codeSnippets["curl"] ?? ""
  );
  const [copyText, setCopiedText] = useState<string>("Copy");

  useEffect(() => {
    setSelectedText(codeSnippets[selectedCode] ?? "");
  }, [codeSnippets, selectedCode]);

  const selectType = async (type: string) => {
    setSelectedCode(type);
    setSelectedText(codeSnippets[type] ?? "");
  };

  const handleCopy = async (text: string) => {
    await copyToClipboard(text, {
      onSuccess: () => setCopiedText("Copied.."),
      onError: () => setCopiedText("Failed to copy"),
    });
  };

  useEffect(() => {
    const timeout = setTimeout(() => {
      setCopiedText("Copy");
    }, 3000);

    return () => clearTimeout(timeout);
  }, [copyText]);

  const endpointDropdownItems = endpointConfigs.map((config) => ({
    key: config.key,
    label: (
      <div className="flex flex-col">
        {/* <Text_12_400_EEEEEE>{config.label}</Text_12_400_EEEEEE> */}
        <Text_12_400_EEEEEE>{(config.path)}</Text_12_400_EEEEEE>
      </div>
    ),
    onClick: () => setSelectedEndpointKey(config.key),
  }));

  const selectedEndpointLabel =
    selectedEndpoint?.label ?? endpointTemplates.chat.label;
  const selectedEndpointPath =
    selectedEndpoint?.path ?? endpointTemplates.chat.defaultPath;
  const selectedEndpointPathDisplay = selectedEndpointPath;

  return (
    <BudForm data={{}}>
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerCard>
            <div className="py-[.25rem]">
              <div className="flex justify-start items-center">
                <div className="text-[#EEEEEE] text-[1.125rem] leadign-[100%]">
                  {drawerProps?.endpoint?.name ||
                    drawerProps?.name ||
                    clusterDetails?.name}
                </div>
              </div>
              <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem] flex-wrap">
                {tags.map((item, index) => (
                  item.name ? <Tags key={index} name={item.name} color={item.color} /> : null
                ))}
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerCard>
            <div className="pt-[.9rem]">
              <Text_20_400_FFFFFF className="tracking-[.03rem]">
                Code Snippet
              </Text_20_400_FFFFFF>
              <Text_12_400_757575 className="tracking-[.004rem] mt-[1rem]">
                Copy the code below and use it for deployment
              </Text_12_400_757575>
            </div>
            <div className="pt-[1.4rem] flex flex-row gap-[1rem] items-start">
              <div className="flex-1">
                <CustomDropDown
                  isDisabled={endpointConfigs.length <= 1}
                  Placement="bottomLeft"
                  buttonContent={
                    <div className="border border-[.5px] border-[#965CDE] rounded-[6px] bg-[#1E0C34] min-h-[2.25rem] flex items-center justify-between w-full px-[.75rem] py-[.5rem]">
                      <div className="flex flex-col items-start text-left">
                        {/* <Text_12_600_EEEEEE className="leading-[1.1]">
                          {selectedEndpointLabel}
                        </Text_12_600_EEEEEE> */}
                        <Text_12_600_EEEEEE className="leading-[1.1]">
                          {selectedEndpointPathDisplay}
                        </Text_12_600_EEEEEE>
                      </div>
                      <ChevronDown className="w-[1rem] text-[#EEEEEE] text-[.75rem]" />
                    </div>
                  }
                  items={endpointDropdownItems}
                />
              </div>
              <div className="flex-shrink-0">
                <CustomDropDown
                  Placement="bottomLeft"
                  buttonContent={
                    <div className="border border-[.5px] border-[#965CDE] rounded-[6px] bg-[#1E0C34] min-w-[4rem] min-h-[2.25rem] flex items-center justify-center px-[.75rem] py-[.5rem]">
                      <Text_12_600_EEEEEE className="flex items-center justify-center">
                        {selectedCode.charAt(0).toUpperCase() +
                          selectedCode.slice(1)}
                      </Text_12_600_EEEEEE>
                      <ChevronDown className="w-[1rem] text-[#EEEEEE] text-[.75rem] ml-[.15rem]" />
                    </div>
                  }
                  items={[
                    {
                      key: "1",
                      label: <Text_12_400_EEEEEE>Curl</Text_12_400_EEEEEE>,
                      onClick: () => selectType("curl"),
                    },
                    {
                      key: "2",
                      label: <Text_12_400_EEEEEE>Python</Text_12_400_EEEEEE>,
                      onClick: () => selectType("python"),
                    },
                    {
                      key: "3",
                      label: <Text_12_400_EEEEEE>JavaScript</Text_12_400_EEEEEE>,
                      onClick: () => selectType("javascript"),
                    },
                  ]}
                />
              </div>
            </div>
            <div className="custom-code rounded-[8px] relative bg-[#FFFFFF08] mt-[1.5rem] w-full overflow-hidden">
              <CustomPopover
                title={copyText}
                contentClassNames="py-[.3rem]"
                Placement="topRight"
              >
                <div
                  className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center absolute right-[0.35rem] top-[0.65rem] cursor-pointer hover:bg-[#1F1F1F]"
                  onClick={() => handleCopy(selectedText)}
                >
                  <Image
                    preview={false}
                    src="/images/drawer/Copy.png"
                    alt="info"
                    style={{ height: ".75rem" }}
                  />
                </div>
              </CustomPopover>
              <div className="markdown-body">
                {" "}
                <SyntaxHighlighter language="bash" style={oneDark} showLineNumbers>
                  {selectedText.replace(/^```[\w]*\n/, "").replace(/```$/, "")}
                </SyntaxHighlighter>
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
