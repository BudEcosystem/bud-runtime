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
import CustomDropDown from "../components/CustomDropDown";
import { ChevronDown } from "lucide-react";
import CustomPopover from "../components/customPopover";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDrawer } from "src/hooks/useDrawer";
import { copyToClipboard } from "@/utils/clipboard";

type EndpointConfig = {
  key: string;
  label: string;
  path: string;
  payload: Record<string, unknown>;
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
  return `curl --location '${apiUrl}' \\
  --header 'Authorization: Bearer {API_KEY_HERE}' \\
  --header 'Content-Type: application/json' \\
  --data '${JSON.stringify(config.payload, null, 2)}'`;
};

const generatePythonCode = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) return "";
  return `import requests
import json

url = "${apiUrl}"
payload = json.dumps(${JSON.stringify(config.payload, null, 2)})
headers = {
  'Authorization': 'Bearer {API_KEY_HERE}',
  'Content-Type': 'application/json'
}

response = requests.post(url, headers=headers, data=payload)
print(response.text)`;
};

const generateJavaScriptCode = (apiUrl: string, config?: EndpointConfig) => {
  if (!config) return "";
  return `const data = ${JSON.stringify(config.payload, null, 2)};

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
};

export default function UseGuardrail() {
  const { drawerProps } = useDrawer();

  // Get guardrail ID from the guardrail record passed via drawer props
  const guardrailId = drawerProps?.guardrail?.id || "GUARDRAIL_PROFILE_ID";
  const guardrailName = drawerProps?.guardrail?.name || "Guardrail";

  // Endpoint configuration for guardrails
  const endpointConfig = useMemo<EndpointConfig>(() => {
    return {
      key: "/v1/guardrails/check",
      label: "Check Content",
      path: "/v1/guardrails/check",
      payload: {
        profile_id: guardrailId,
        input: "Text content to be validated by the guardrail",
        config: {
          action: "block",
          return_details: true
        }
      },
    };
  }, [guardrailId]);

  const baseUrl =
    process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BASE_URL ||
    "";
  const apiUrl = joinBaseWithPath(baseUrl, endpointConfig.path);

  const codeSnippets = useMemo(
    () => ({
      curl: generateCurlCommand(apiUrl, endpointConfig),
      python: generatePythonCode(apiUrl, endpointConfig),
      javascript: generateJavaScriptCode(apiUrl, endpointConfig),
    }),
    [apiUrl, endpointConfig]
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

  return (
    <BudForm data={{}}>
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerCard>
            <div className="pt-[.9rem]">
              <Text_20_400_FFFFFF className="tracking-[.03rem]">
                Code Snippet
              </Text_20_400_FFFFFF>
              <Text_12_400_757575 className="tracking-[.004rem] mt-[1rem]">
                Copy the code below to use the <strong>{guardrailName}</strong> guardrail in your application
              </Text_12_400_757575>
            </div>
            <div className="pt-[1.4rem] flex flex-row gap-[1rem] items-start justify-start">
              <div className="flex-shrink-0">
                <CustomDropDown
                  Placement="bottomLeft"
                  buttonContent={
                    <div className="border border-[.5px] border-[#965CDE] rounded-[6px] bg-[#1E0C34] min-w-[4rem] min-h-[1.25rem] flex items-center justify-center px-[.75rem] py-[.1rem]">
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
