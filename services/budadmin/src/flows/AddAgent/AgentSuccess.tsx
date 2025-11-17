import React, { useEffect, useMemo, useState } from "react";
import { Image, Tag } from "antd";
import { useRouter } from "next/router";
import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_16_600_FFFFFF, Text_14_400_EEEEEE, Text_12_400_757575, Text_20_400_FFFFFF, Text_12_600_EEEEEE, Text_12_400_EEEEEE } from "@/components/ui/text";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { ModelFlowInfoCard } from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { useAddAgent } from "@/stores/useAddAgent";
import { usePromptsAgents } from "@/stores/usePromptsAgents";
import CustomDropDown from "../components/CustomDropDown";
import CustomPopover from "../components/customPopover";
import { ChevronDown } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { copyToClipboard } from "@/utils/clipboard";

type EndpointConfig = {
  key: string;
  label: string;
  path: string;
  payload: Record<string, unknown>;
};

const ensureLeadingSlash = (path: string) => {
  if (!path) return "";
  return path.startsWith("/") ? path : `/${path}`;
};

const stripLeadingSlash = (path: string) =>
  path.startsWith("/") ? path.slice(1) : path;

const joinBaseWithPath = (base: string, path: string) => {
  if (!base) return stripLeadingSlash(path);
  const normalizedBase = base.endsWith("/") ? base : `${base}/`;
  const normalizedPath = stripLeadingSlash(path);
  return `${normalizedBase}${normalizedPath}`;
};

const generateCurlCommand = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) return "";
  return `curl --location '${apiUrl}' \\\n  --header 'Authorization: Bearer {API_KEY_HERE}' \\\n  --header 'Content-Type: application/json' \\\n  --data '${JSON.stringify(config.payload, null, 2)}'`;
};

const generatePythonCode = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) return "";
  return `import requests\nimport json\n\nurl = "${apiUrl}"\npayload = json.dumps(${JSON.stringify(
    config.payload,
    null,
    2
  )})\nheaders = {\n  'Authorization': 'Bearer {API_KEY_HERE}',\n  'Content-Type': 'application/json'\n}\n\nresponse = requests.post(url, headers=headers, data=payload)\nprint(response.text)`;
};

const generateJavaScriptCode = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) return "";
  return `const data = ${JSON.stringify(config.payload, null, 2)};\n\nfetch('${apiUrl}', {\n  method: 'POST',\n  headers: {\n    'Authorization': 'Bearer {API_KEY_HERE}',\n    'Content-Type': 'application/json'\n  },\n  body: JSON.stringify(data)\n})\n.then(response => response.json())\n.then(data => console.log(data))\n.catch(error => console.error('Error:', error));`;
};

export default function AgentSuccess() {
  const router = useRouter();
  const { closeDrawer } = useDrawer();
  const { fetchPrompts } = usePromptsAgents();

  // Get data from the Add Agent store
  const {
    currentWorkflow,
    deploymentConfiguration,
    reset
  } = useAddAgent();

  // Remove 'agent' and 'prompt' query parameters from URL
  useEffect(() => {
    if (!router.isReady) return;

    const { agent, prompt } = router.query;

    // Only attempt removal if parameters exist
    if (agent || prompt) {
      const currentPath = window.location.pathname;
      const urlSearchParams = new URLSearchParams(window.location.search);

      // Remove agent and prompt parameters
      urlSearchParams.delete('agent');
      urlSearchParams.delete('prompt');

      const newUrl = urlSearchParams.toString()
        ? `${currentPath}?${urlSearchParams.toString()}`
        : currentPath;

      // Use window.history.replaceState to avoid triggering router events
      window.history.replaceState(
        { ...window.history.state },
        '',
        newUrl
      );
    }
  }, [router.isReady, router.query.agent, router.query.prompt]);

  useEffect(() => {
    // Clean up the store when component unmounts (drawer closes)
    return () => {
      reset();
    };
  }, [reset]);

  // Get model from workflow steps
  const model = currentWorkflow?.workflow_steps?.model;

  const handleClose = () => {
    // Refresh the prompts list
    fetchPrompts();
    // Close the drawer
    closeDrawer();
  };

  // Code snippet functionality
  const promptName = deploymentConfiguration?.deploymentName || "PROMPT_NAME";

  const endpointConfigs = useMemo<EndpointConfig[]>(() => {
    return [
      {
        key: "/v1/chat/completions",
        label: "Chat Completions",
        path: "/v1/chat/completions",
        payload: {
          prompt: {
            name: promptName,
            version: "1",
            variables: {
              variable_1: "Value 1",
              variable_2: "Value 2"
            }
          },
          input: "Unstructured input text related to the prompt."
        },
      },
      {
        key: "/v1/completions",
        label: "Completions",
        path: "/v1/completions",
        payload: {
          prompt: {
            name: promptName,
            version: "1",
            variables: {
              variable_1: "Value 1",
              variable_2: "Value 2"
            }
          },
          input: "Unstructured input text related to the prompt."
        },
      }
    ];
  }, [promptName]);

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
        <Text_12_400_EEEEEE>{config.path}</Text_12_400_EEEEEE>
      </div>
    ),
    onClick: () => setSelectedEndpointKey(config.key),
  }));

  const selectedEndpointPathDisplay = selectedEndpoint?.path || "/v1/chat/completions";

  return (
    <BudForm
      data={{}}
      backText="Close"
      onBack={handleClose}
    >
      <BudWraperBox >
        <BudDrawerLayout>
          <DrawerTitleCard
              title={"Prompt Deployed"}
              description={`${deploymentConfiguration?.deploymentName} prompt has been deployed`}
            />
            <ModelFlowInfoCard
              selectedModel={model}
              informationSpecs={[
                {
                  name: "URI",
                  value: model?.uri,
                  full: true,
                  icon: "/images/drawer/tag.png",
                },
              ]}
            />
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
              <div className="flex-shrink-0">
                <CustomDropDown
                  Placement="bottomLeft"
                  buttonContent={
                    <div className="border border-[.5px] border-[#965CDE] rounded-[6px] bg-[#1E0C34] min-w-[4rem] min-h-[1.25rem] flex items-center justify-center px-[.75rem] pt-[.1rem]">
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
                <SyntaxHighlighter language={selectedCode === 'curl' ? 'bash' : selectedCode} style={oneDark} showLineNumbers>
                  {selectedText}
                </SyntaxHighlighter>
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
