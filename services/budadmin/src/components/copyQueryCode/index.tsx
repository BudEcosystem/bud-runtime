import React from "react";
import CustomDropdownMenu from "../ui/dropDown";
const selectItems = ["Copy for curl", "Copy for python", "Copy for javascript"];
import { errorToast, successToast } from "../toast";
import { copyToClipboard } from "@/utils/clipboard";

const CopyQuery = ({ Data, RenderItem, triggerClassNames }: any) => {
  // Function to determine the appropriate endpoint and payload
  const getEndpointConfig = () => {
    const supportedEndpoints = Data?.endpoint?.model?.supported_endpoints;
    const modelName = Data?.endpoint?.model?.name || "";

    // Default to chat endpoint
    let endpoint = "v1/chat/completions";
    let payloadExample: any = {
      model: modelName,
      max_tokens: 256,
      messages: [{ role: "user", content: "Summarize the given text" }],
    };

    if (supportedEndpoints) {
      // Check for embedding endpoint
      if (supportedEndpoints.embedding?.enabled) {
        endpoint = supportedEndpoints.embedding.path || "v1/embeddings";
        payloadExample = {
          model: modelName,
          input: "Your text to embed",
        };
      }
      // Check for audio transcription endpoint
      else if (supportedEndpoints.audio_transcription?.enabled) {
        endpoint =
          supportedEndpoints.audio_transcription.path ||
          "v1/audio/transcriptions";
        payloadExample = {
          model: modelName,
          file: "@/path/to/audio.mp3",
          response_format: "json",
        };
      }
      // Check for text-to-speech endpoint
      else if (supportedEndpoints.audio_speech?.enabled) {
        endpoint = supportedEndpoints.audio_speech.path || "v1/audio/speech";
        payloadExample = {
          model: modelName,
          input: "Text to convert to speech",
          voice: "alloy",
        };
      }
      // Check for image generation endpoint
      else if (supportedEndpoints.image_generation?.enabled) {
        endpoint =
          supportedEndpoints.image_generation.path || "v1/images/generations";
        payloadExample = {
          model: modelName,
          prompt: "A cute baby sea otter",
          n: 1,
          size: "1024x1024",
        };
      }
    }

    return { endpoint, payloadExample };
  };

  const handleSelect = async (value: string) => {
    const { endpoint, payloadExample } = getEndpointConfig();
    // Use the base URL without any endpoint path appended
    const baseUrl =
      process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL ||
      process.env.NEXT_PUBLIC_BASE_URL ||
      "";
    const apiUrl = `${baseUrl.replace( /\/+$/, '')}/${endpoint}`;

    let curl: string, python: string, js: string;

    // Special handling for audio transcription (file upload)
    if (endpoint.includes("audio/transcriptions")) {
      curl = `curl --location '${apiUrl}' \\
                  --header 'Authorization: Bearer {API_KEY_HERE}' \\
                  --form 'file=@"/path/to/audio.mp3"' \\
                  --form 'model="${payloadExample.model}"' \\
                  --form 'response_format="json"'`;

      python = `import requests

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

      js = `const formData = new FormData();
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
    } else {
      // Standard JSON payload endpoints
      curl = `curl --location '${apiUrl}' \\
                  --header 'Authorization: Bearer {API_KEY_HERE}' \\
                  --header 'Content-Type: application/json' \\
                  --data '${JSON.stringify(payloadExample, null, 2)}'`;

      python = `import requests
                    import json

                    url = "${apiUrl}"
                    payload = json.dumps(${JSON.stringify(payloadExample, null, 2)})
                    headers = {
                      'Authorization': 'Bearer {API_KEY_HERE}',
                      'Content-Type': 'application/json'
                    }

                    response = requests.post(url, headers=headers, data=payload)
                    print(response.text)`;

      js = `const data = ${JSON.stringify(payloadExample, null, 2)};

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
    }

    let text: string;
    if (value === "Copy for curl") {
      text = curl;
    } else if (value === "Copy for python") {
      text = python;
    } else if (value === "Copy for javascript") {
      text = js;
    }

    await copyToClipboard(text, {
      onSuccess: () => successToast("Copied.."),
      onError: () => errorToast("Failed to copy"),
    });
  };

  return (
    <>
      <CustomDropdownMenu
        // contentRenderItem={
        //   selectItems.map((item, index) => (
        //     <Text_12_400_FFFFFF key={index}>{item}</Text_12_400_FFFFFF>
        //   ))
        // }
        items={selectItems}
        onSelect={handleSelect}
        triggerClassNames={triggerClassNames}
        contentClassNames="text-nowrap"
        triggerRenderItem={RenderItem}
      />
    </>
  );
};

export default CopyQuery;
