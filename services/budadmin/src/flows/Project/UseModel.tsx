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
import React, { useEffect, useState } from "react";
import Tags from "../components/DrawerTags";
import CustomDropDown from "../components/CustomDropDown";
import { ChevronDown } from "lucide-react";
import { useEndPoints } from "src/hooks/useEndPoint";
import CustomPopover from "../components/customPopover";

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDrawer } from "src/hooks/useDrawer";

export default function UseModel() {
  const { drawerProps } = useDrawer();
  const { clusterDetails } = useEndPoints();

  const tags = [
    {
      name:
        drawerProps?.endpoint?.model?.name ||
        drawerProps?.name ||
        clusterDetails?.model?.name,
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

  // Function to get the appropriate endpoint and payload based on model type
  const getEndpointConfig = () => {
    // Get model name from various sources
    const modelName =
      drawerProps?.endpoint?.name || drawerProps?.name || clusterDetails?.name;

    // Get supported endpoints from drawerProps.endpoint (from endpoints list API) or fallback to model supported_endpoints
    const endpointSupportedEndpoints =
      drawerProps?.endpoint?.supported_endpoints; // This is an array from the endpoints API
    const modelSupportedEndpoints =
      drawerProps?.endpoint?.model?.supported_endpoints ||
      clusterDetails?.model?.supported_endpoints; // This is an object from model data

    // Default to chat endpoint
    let endpoint = "v1/chat/completions";
    let payloadExample: any = {
      model: modelName,
      max_tokens: 256,
      messages: [{ role: "user", content: "Summarize the given text" }],
    };

    // First check the endpoints array from the API response
    if (
      endpointSupportedEndpoints &&
      Array.isArray(endpointSupportedEndpoints)
    ) {
      // The API returns an array of endpoint paths like ["/v1/embeddings", "/v1/chat/completions"]
      if (endpointSupportedEndpoints.includes("/v1/embeddings")) {
        endpoint = "v1/embeddings";
        payloadExample = {
          model: modelName,
          input: "Your text to embed",
        };
      } else if (
        endpointSupportedEndpoints.includes("/v1/audio/transcriptions")
      ) {
        endpoint = "v1/audio/transcriptions";
        payloadExample = {
          model: modelName,
          file: "@/path/to/audio.mp3",
          response_format: "json",
        };
      } else if (endpointSupportedEndpoints.includes("/v1/audio/speech")) {
        endpoint = "v1/audio/speech";
        payloadExample = {
          model: modelName,
          input: "Text to convert to speech",
          voice: "alloy",
        };
      } else if (
        endpointSupportedEndpoints.includes("/v1/images/generations")
      ) {
        endpoint = "v1/images/generations";
        payloadExample = {
          model: modelName,
          prompt: "A cute baby sea otter",
          n: 1,
          size: "1024x1024",
        };
      } else if (endpointSupportedEndpoints.includes("/v1/completions")) {
        endpoint = "v1/completions";
        payloadExample = {
          model: modelName,
          prompt: "Once upon a time",
          max_tokens: 256,
        };
      } else if (endpointSupportedEndpoints.includes("/v1/chat/completions")) {
        endpoint = "v1/chat/completions";
      }
    }
    // Fallback to model supported endpoints object structure
    else if (modelSupportedEndpoints) {
      // Check for embedding endpoint
      if (modelSupportedEndpoints.embedding?.enabled) {
        endpoint = modelSupportedEndpoints.embedding.path || "v1/embeddings";
        payloadExample = {
          model: modelName,
          input: "Your text to embed",
        };
      }
      // Check for audio transcription endpoint
      else if (modelSupportedEndpoints.audio_transcription?.enabled) {
        endpoint =
          modelSupportedEndpoints.audio_transcription.path ||
          "v1/audio/transcriptions";
        payloadExample = {
          model: modelName,
          file: "@/path/to/audio.mp3",
          response_format: "json",
        };
      }
      // Check for text-to-speech endpoint
      else if (modelSupportedEndpoints.audio_speech?.enabled) {
        endpoint =
          modelSupportedEndpoints.audio_speech.path || "v1/audio/speech";
        payloadExample = {
          model: modelName,
          input: "Text to convert to speech",
          voice: "alloy",
        };
      }
      // Check for image generation endpoint
      else if (modelSupportedEndpoints.image_generation?.enabled) {
        endpoint =
          modelSupportedEndpoints.image_generation.path ||
          "v1/images/generations";
        payloadExample = {
          model: modelName,
          prompt: "A cute baby sea otter",
          n: 1,
          size: "1024x1024",
        };
      }
      // Check for completion endpoint
      else if (modelSupportedEndpoints.completion?.enabled) {
        endpoint = modelSupportedEndpoints.completion.path || "v1/completions";
        payloadExample = {
          model: modelName,
          prompt: "Once upon a time",
          max_tokens: 256,
        };
      }
      // Default to chat if it's enabled
      else if (modelSupportedEndpoints.chat?.enabled) {
        endpoint = modelSupportedEndpoints.chat.path || "v1/chat/completions";
      }
    }

    return { endpoint, payloadExample };
  };

  const { endpoint, payloadExample } = getEndpointConfig();
  // Use the base URL from environment variable, not the one with /v1/chat/completions appended
  const baseUrl =
    process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BASE_URL ||
    "";
  const apiUrl = `${baseUrl}${endpoint}`;

  const generateCurlCommand = () => {
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
  };

  const generatePythonCode = () => {
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
  };

  const generateJavaScriptCode = () => {
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
  };

  const codeSnippets = {
    curl: generateCurlCommand(),
    python: generatePythonCode(),
    javascript: generateJavaScriptCode(),
  };

  const [selectedCode, setSelectedCode] = useState("curl");
  const [selectedText, setSelectedText] = useState(codeSnippets[selectedCode]);
  const [copyText, setCopiedText] = useState<string>("Copy");

  // Update selected text when endpoint changes
  useEffect(() => {
    setSelectedText(codeSnippets[selectedCode]);
  }, [endpoint, selectedCode]);

  const selectType = async (type: string) => {
    const text = codeSnippets[type];
    setSelectedCode(type);
    setSelectedText(text);
  };

  const handleCopy = (text: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        // message.success('Text copied to clipboard!');
        setCopiedText("Copied..");
      })
      .catch(() => {
        // message.error('Failed to copy text.');
        setCopiedText("Failed to copy");
      });
  };

  useEffect(() => {
    setTimeout(() => {
      setCopiedText("Copy");
    }, 3000);
  }, [copyText]);

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
              <div className="flex items-center justify-start gap-[.5rem] mt-[.3rem] flex-wrap	">
                {tags.map((item, index) => (
                  <Tags key={index} name={item.name} color={item.color} />
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
            <div className="pt-[1.4rem]">
              <CustomDropDown
                Placement="bottomLeft"
                buttonContent={
                  <div className="border border-[.5px] border-[#965CDE] rounded-[6px] bg-[#1E0C34] min-w-[4rem] min-h-[1.75rem] flex items-center justify-center px-[.6rem]">
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
              {/* <MemoizedMarkdown content={selectedText} id={"code-block"} /> */}
              {/* <pre className="ibm text-[.75rem] text-[#EEEEEE] whitespace-pre-wrap">
                {selectedText}
              </pre> */}
              <div className="markdown-body">
                {" "}
                {/* optional styling */}
                <SyntaxHighlighter
                  language="bash"
                  // dark, oneDark, dracula, atomDark, coldarkDark, materialDark, vs, vscDarkPlus
                  style={oneDark}
                  showLineNumbers
                >
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
