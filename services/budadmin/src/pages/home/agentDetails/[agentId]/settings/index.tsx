import React from "react";
import { Input, InputNumber, Select, Switch, Button } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";

const { TextArea } = Input;

interface SettingsTabProps {
  agentData?: any;
}

const SettingsTab: React.FC<SettingsTabProps> = ({ agentData }) => {
  const [formData, setFormData] = React.useState({
    name: agentData?.name || "",
    description: agentData?.description || "",
    model: "gpt-4",
    temperature: 0.7,
    maxTokens: 2048,
    topP: 1.0,
    frequencyPenalty: 0,
    presencePenalty: 0,
    enableStreaming: true,
    enableLogging: true,
  });

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="px-[3.5rem] pb-8">
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
        <Text_14_600_EEEEEE className="mb-6 block">Agent Settings</Text_14_600_EEEEEE>

        <div className="space-y-6">
          {/* Basic Information */}
          <div>
            <Text_12_600_EEEEEE className="block mb-2">Name</Text_12_600_EEEEEE>
            <Input
              value={formData.name}
              onChange={(e) => handleChange("name", e.target.value)}
              placeholder="Enter agent name"
            />
          </div>

          <div>
            <Text_12_600_EEEEEE className="block mb-2">Description</Text_12_600_EEEEEE>
            <TextArea
              value={formData.description}
              onChange={(e) => handleChange("description", e.target.value)}
              placeholder="Enter agent description"
              rows={4}
            />
          </div>

          {/* Model Configuration */}
          <div className="border-t border-[#1F1F1F] pt-6">
            <Text_14_600_EEEEEE className="mb-4 block">Model Configuration</Text_14_600_EEEEEE>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Text_12_600_EEEEEE className="block mb-2">Model</Text_12_600_EEEEEE>
                <Select
                  value={formData.model}
                  onChange={(value) => handleChange("model", value)}
                  className="w-full"
                  options={[
                    { label: "GPT-4", value: "gpt-4" },
                    { label: "GPT-3.5 Turbo", value: "gpt-3.5-turbo" },
                    { label: "Claude 3", value: "claude-3" },
                  ]}
                />
              </div>

              <div>
                <Text_12_600_EEEEEE className="block mb-2">Temperature</Text_12_600_EEEEEE>
                <InputNumber
                  value={formData.temperature}
                  onChange={(value) => handleChange("temperature", value)}
                  min={0}
                  max={2}
                  step={0.1}
                  className="w-full"
                />
                <Text_12_400_B3B3B3 className="block mt-1">
                  Controls randomness: 0 is focused, 2 is creative
                </Text_12_400_B3B3B3>
              </div>

              <div>
                <Text_12_600_EEEEEE className="block mb-2">Max Tokens</Text_12_600_EEEEEE>
                <InputNumber
                  value={formData.maxTokens}
                  onChange={(value) => handleChange("maxTokens", value)}
                  min={1}
                  max={4096}
                  className="w-full"
                />
                <Text_12_400_B3B3B3 className="block mt-1">
                  Maximum length of the response
                </Text_12_400_B3B3B3>
              </div>

              <div>
                <Text_12_600_EEEEEE className="block mb-2">Top P</Text_12_600_EEEEEE>
                <InputNumber
                  value={formData.topP}
                  onChange={(value) => handleChange("topP", value)}
                  min={0}
                  max={1}
                  step={0.1}
                  className="w-full"
                />
                <Text_12_400_B3B3B3 className="block mt-1">
                  Controls diversity via nucleus sampling
                </Text_12_400_B3B3B3>
              </div>

              <div>
                <Text_12_600_EEEEEE className="block mb-2">Frequency Penalty</Text_12_600_EEEEEE>
                <InputNumber
                  value={formData.frequencyPenalty}
                  onChange={(value) => handleChange("frequencyPenalty", value)}
                  min={-2}
                  max={2}
                  step={0.1}
                  className="w-full"
                />
                <Text_12_400_B3B3B3 className="block mt-1">
                  Reduces repetition of token sequences
                </Text_12_400_B3B3B3>
              </div>

              <div>
                <Text_12_600_EEEEEE className="block mb-2">Presence Penalty</Text_12_600_EEEEEE>
                <InputNumber
                  value={formData.presencePenalty}
                  onChange={(value) => handleChange("presencePenalty", value)}
                  min={-2}
                  max={2}
                  step={0.1}
                  className="w-full"
                />
                <Text_12_400_B3B3B3 className="block mt-1">
                  Reduces repetition of topics
                </Text_12_400_B3B3B3>
              </div>
            </div>
          </div>

          {/* Features */}
          <div className="border-t border-[#1F1F1F] pt-6">
            <Text_14_600_EEEEEE className="mb-4 block">Features</Text_14_600_EEEEEE>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <Text_12_600_EEEEEE className="block mb-1">Enable Streaming</Text_12_600_EEEEEE>
                  <Text_12_400_B3B3B3>
                    Stream responses as they are generated
                  </Text_12_400_B3B3B3>
                </div>
                <Switch
                  checked={formData.enableStreaming}
                  onChange={(checked) => handleChange("enableStreaming", checked)}
                />
              </div>

              <div className="flex justify-between items-center">
                <div>
                  <Text_12_600_EEEEEE className="block mb-1">Enable Logging</Text_12_600_EEEEEE>
                  <Text_12_400_B3B3B3>
                    Log all requests and responses for debugging
                  </Text_12_400_B3B3B3>
                </div>
                <Switch
                  checked={formData.enableLogging}
                  onChange={(checked) => handleChange("enableLogging", checked)}
                />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3 pt-6 border-t border-[#1F1F1F]">
            <Button>Cancel</Button>
            <Button type="primary">Save Changes</Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsTab;
