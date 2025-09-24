import React, { useState, useEffect } from "react";
import { Modal, Input, Tag, Button, Empty } from "antd";
import { SearchOutlined, RobotOutlined, CloseOutlined } from "@ant-design/icons";
import { useAgentStore } from "@/stores/useAgentStore";

interface Model {
  id: string;
  name: string;
  provider: string;
  type: string;
  description?: string;
  tags?: string[];
  isLoaded?: boolean;
}

// Mock models for demonstration - replace with actual API call
const mockModels: Model[] = [
  {
    id: "gpt-3.5-turbo",
    name: "GPT 3.5 Turbo",
    provider: "OpenAI",
    type: "Chat",
    description: "Fast and efficient model for general purposes",
    tags: ["fast", "general", "chat"],
    isLoaded: true,
  },
  {
    id: "gpt-4",
    name: "GPT 4",
    provider: "OpenAI",
    type: "Chat",
    description: "Most capable model for complex tasks",
    tags: ["advanced", "reasoning", "chat"],
    isLoaded: true,
  },
  {
    id: "claude-3-opus",
    name: "Claude 3 Opus",
    provider: "Anthropic",
    type: "Chat",
    description: "Powerful model with strong reasoning capabilities",
    tags: ["reasoning", "analysis", "chat"],
    isLoaded: false,
  },
  {
    id: "claude-3-sonnet",
    name: "Claude 3 Sonnet",
    provider: "Anthropic",
    type: "Chat",
    description: "Balanced performance and speed",
    tags: ["balanced", "efficient", "chat"],
    isLoaded: false,
  },
  {
    id: "llama-3-70b",
    name: "Llama 3 70B",
    provider: "Meta",
    type: "Chat",
    description: "Open source large language model",
    tags: ["opensource", "large", "chat"],
    isLoaded: false,
  },
];

const AgentSelector: React.FC = () => {
  const { isModelSelectorOpen, closeModelSelector, selectedSessionId, updateSession } = useAgentStore();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedTab, setSelectedTab] = useState<"loaded" | "available">("loaded");
  const [filteredModels, setFilteredModels] = useState<Model[]>([]);

  useEffect(() => {
    const filtered = mockModels.filter((model) => {
      const matchesSearch =
        model.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        model.provider.toLowerCase().includes(searchTerm.toLowerCase()) ||
        model.tags?.some((tag) => tag.toLowerCase().includes(searchTerm.toLowerCase()));

      const matchesTab = selectedTab === "loaded" ? model.isLoaded : !model.isLoaded;

      return matchesSearch && matchesTab;
    });
    setFilteredModels(filtered);
  }, [searchTerm, selectedTab]);

  const handleSelectModel = (model: Model) => {
    if (selectedSessionId) {
      updateSession(selectedSessionId, {
        modelId: model.id,
        modelName: model.name,
      });
    }
    closeModelSelector();
  };

  const ModelCard = ({ model }: { model: Model }) => (
    <div
      className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-4 cursor-pointer hover:border-[#965CDE] transition-colors"
      onClick={() => handleSelectModel(model)}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <RobotOutlined className="text-[#965CDE]" />
          <div>
            <h4 className="text-[#EEEEEE] text-sm font-medium m-0">{model.name}</h4>
            <p className="text-[#808080] text-xs m-0">{model.provider}</p>
          </div>
        </div>
        {model.isLoaded && (
          <Tag className="bg-[#1A3A1A] border-[#2A5A2A] text-[#4ADE80] text-xs">Loaded</Tag>
        )}
      </div>
      {model.description && (
        <p className="text-[#B3B3B3] text-xs mb-2 line-clamp-2">{model.description}</p>
      )}
      {model.tags && model.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {model.tags.map((tag, index) => (
            <Tag
              key={index}
              className="bg-[#1F1F1F] border-[#2A2A2A] text-[#808080] text-xs px-2 py-0"
            >
              {tag}
            </Tag>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <Modal
      open={isModelSelectorOpen}
      onCancel={closeModelSelector}
      width={800}
      footer={null}
      className="agent-selector-modal"
      closeIcon={<CloseOutlined className="text-[#808080] hover:text-[#EEEEEE]" />}
      styles={{
        mask: { backgroundColor: "rgba(0, 0, 0, 0.6)" },
        content: {
          backgroundColor: "#0A0A0A",
          border: "1px solid #1F1F1F",
          borderRadius: "12px",
        },
        header: {
          backgroundColor: "#0A0A0A",
          borderBottom: "1px solid #1F1F1F",
        },
      }}
    >
      <div className="p-6">
        <h2 className="text-[#EEEEEE] text-lg font-semibold mb-4">Select Model</h2>

        {/* Search Bar */}
        <Input
          placeholder="Search models..."
          prefix={<SearchOutlined className="text-[#808080]" />}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="mb-4 bg-[#101010] border-[#2A2A2A] text-[#EEEEEE] placeholder-[#606060]"
          allowClear
        />

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          <Button
            type={selectedTab === "loaded" ? "primary" : "default"}
            onClick={() => setSelectedTab("loaded")}
            className={
              selectedTab === "loaded"
                ? "bg-[#965CDE] border-none"
                : "bg-transparent border-[#2A2A2A] text-[#808080]"
            }
          >
            Currently Loaded
          </Button>
          <Button
            type={selectedTab === "available" ? "primary" : "default"}
            onClick={() => setSelectedTab("available")}
            className={
              selectedTab === "available"
                ? "bg-[#965CDE] border-none"
                : "bg-transparent border-[#2A2A2A] text-[#808080]"
            }
          >
            Available Models
          </Button>
        </div>

        {/* Models Grid */}
        <div className="max-h-[400px] overflow-y-auto">
          {filteredModels.length > 0 ? (
            <div className="grid grid-cols-2 gap-4">
              {filteredModels.map((model) => (
                <ModelCard key={model.id} model={model} />
              ))}
            </div>
          ) : (
            <Empty
              description={
                <span className="text-[#808080]">
                  {searchTerm
                    ? `No models found matching "${searchTerm}"`
                    : `No ${selectedTab === "loaded" ? "loaded" : "available"} models`}
                </span>
              }
              className="py-8"
            />
          )}
        </div>
      </div>
    </Modal>
  );
};

export default AgentSelector;
