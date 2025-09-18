import React, { useState, useEffect, useRef } from "react";
import { Button, Image, Empty } from "antd";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import BlurModal from "./BlurModal";
import { Text_12_400_EEEEEE } from "../ui/text";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";

interface LoadModelProps {
  sessionId: string;
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

interface ModelEndpoint {
  id: string;
  name: string;
  model?: {
    icon?: string;
    provider?: {
      icon?: string;
    };
  };
  provider?: string;
  description?: string;
  tags?: string[];
}

// Mock endpoints for demonstration - replace with actual API
const mockEndpoints: ModelEndpoint[] = [
  {
    id: "gpt-3.5-turbo",
    name: "GPT 3.5 Turbo",
    provider: "OpenAI",
    description: "Fast and efficient model for general purposes",
    tags: ["fast", "general", "chat"],
    model: {
      provider: {
        icon: "/icons/openai.png"
      }
    }
  },
  {
    id: "gpt-4",
    name: "GPT 4",
    provider: "OpenAI",
    description: "Most capable model for complex tasks",
    tags: ["advanced", "reasoning", "chat"],
    model: {
      provider: {
        icon: "/icons/openai.png"
      }
    }
  },
  {
    id: "claude-3-opus",
    name: "Claude 3 Opus",
    provider: "Anthropic",
    description: "Powerful model with strong reasoning capabilities",
    tags: ["reasoning", "analysis", "chat"],
    model: {
      provider: {
        icon: "/icons/anthropic.png"
      }
    }
  },
  {
    id: "claude-3-sonnet",
    name: "Claude 3 Sonnet",
    provider: "Anthropic",
    description: "Balanced performance and speed",
    tags: ["balanced", "efficient", "chat"],
    model: {
      provider: {
        icon: "/icons/anthropic.png"
      }
    }
  },
  {
    id: "llama-3-70b",
    name: "Llama 3 70B",
    provider: "Meta",
    description: "Open source large language model",
    tags: ["opensource", "large", "chat"],
    model: {
      provider: {
        icon: "/icons/meta.png"
      }
    }
  },
];

const ModelListCard: React.FC<{
  data: ModelEndpoint;
  selected?: boolean;
  selectable?: boolean;
  handleClick: () => void;
}> = ({ data, selected, selectable, handleClick }) => {
  return (
    <div
      onClick={handleClick}
      className={`px-5 py-3 border-b border-[#1F1F1F] hover:bg-[#1A1A1A] cursor-pointer transition-colors ${selected ? "bg-[#1A1A1A]" : ""
        }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Image
            src={data.model?.provider?.icon || "/icons/modelRepoWhite.png"}
            fallback="/icons/modelRepoWhite.png"
            preview={false}
            alt="model"
            width={20}
            height={20}
          />
          <div>
            <div className="text-[#EEEEEE] text-sm font-medium">{data.name}</div>
            {data.description && (
              <div className="text-[#808080] text-xs mt-1">{data.description}</div>
            )}
          </div>
        </div>
        {selectable && (
          <div className="text-[#4ADE80] text-xs">Currently Loaded</div>
        )}
      </div>
      {data.tags && data.tags.length > 0 && (
        <div className="flex gap-1 mt-2 flex-wrap">
          {data.tags.map((tag, index) => (
            <span
              key={index}
              className="text-[#808080] text-[10px] bg-[#1F1F1F] px-2 py-1 rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default function LoadModel({ sessionId, open, setOpen }: LoadModelProps) {
  const { updateSession, sessions } = useAgentStore();
  const session = sessions.find(s => s.id === sessionId);

  const [sortBy] = useState("recency");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [currentlyLoaded, setCurrentlyLoaded] = useState<ModelEndpoint[]>([]);
  const [availableModels, setAvailableModels] = useState<ModelEndpoint[]>([]);
  const [searchValue, setSearchValue] = useState("");
  const [filteredModels, setFilteredModels] = useState<ModelEndpoint[]>([]);

  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Set currently loaded model
    const current = mockEndpoints.filter(
      endpoint => endpoint.id === session?.selectedDeployment?.id
    );
    setCurrentlyLoaded(current);

    // Set available models (excluding currently loaded)
    const available = mockEndpoints.filter(
      endpoint => endpoint.id !== session?.selectedDeployment?.id
    );
    setAvailableModels(available);
  }, [session?.selectedDeployment]);

  useEffect(() => {
    // Filter and sort available models
    let filtered = availableModels.filter(endpoint =>
      endpoint.name.toLowerCase().includes(searchValue.toLowerCase()) ||
      endpoint.tags?.some(tag => tag.toLowerCase().includes(searchValue.toLowerCase()))
    );

    // Sort models
    filtered = filtered.sort((a, b) => {
      if (sortOrder === "asc") {
        return a.name.localeCompare(b.name);
      } else {
        return b.name.localeCompare(a.name);
      }
    });

    setFilteredModels(filtered);
  }, [availableModels, searchValue, sortOrder]);

  const handleSelectModel = (endpoint: ModelEndpoint) => {
    updateSession(sessionId, {
      modelId: endpoint.id,
      modelName: endpoint.name,
      selectedDeployment: {
        id: endpoint.id,
        name: endpoint.name,
        model: endpoint.model
      }
    });
    setOpen(false);
  };

  return (
    <div ref={containerRef}>
      {/* BlurModal */}
      <BlurModal
        open={open}
        onClose={() => setOpen(false)}
        width="520px"
        height="auto"
        containerRef={buttonRef}
      >
        <div className="bg-[#0A0A0A] shadow-[0px_6px_10px_0px_#1F1F1F66] border border-[#1F1F1FB3] rounded-[10px] overflow-hidden">
          {/* Search Bar */}
          <div className="p-5">
            <SearchHeaderInput
              searchValue={searchValue}
              setSearchValue={setSearchValue}
              expanded={true}
              placeholder="Model names, Tags, Tasks, Parameter sizes"
              classNames="w-full h-7 bg-[#1E1E1E] border border-[#3A3A3A] text-white text-xs placeholder-[#606060] !rounded-[4px]"
              iconWidth="12px"
              iconHeight="12px"
            />
          </div>

          {/* Currently Loaded Section */}
          {currentlyLoaded.length > 0 && (
            <div className="border-t border-[#1F1F1F]">
              <div className="flex justify-between items-center px-5 py-2.5">
                <div className="text-[#757575] text-xs">
                  Currently Loaded
                  <span className="text-white text-xs ml-1">
                    {currentlyLoaded.length}
                  </span>
                </div>
              </div>
              <div className="max-h-[120px] overflow-y-auto">
                {currentlyLoaded.map((endpoint) => (
                  <ModelListCard
                    key={endpoint.id}
                    data={endpoint}
                    selectable={true}
                    selected={true}
                    handleClick={() => handleSelectModel(endpoint)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Available Models Section */}
          <div className="border-t border-[#1F1F1F]">
            <div className="flex justify-between items-center px-5 py-2.5">
              <div className="text-[#757575] text-xs">
                Models Available
                <span className="text-white text-xs ml-1">
                  {filteredModels.length}
                </span>
              </div>
              <div
                className="flex items-center gap-1 bg-[#1E1E1E] rounded-md px-2 py-1 cursor-pointer hover:bg-[#2A2A2A] transition-colors"
                onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
              >
                <span className="text-[#B3B3B3] text-[10px] capitalize">
                  {sortBy}
                </span>
                {sortOrder === "asc" ? (
                  <ChevronUp className="w-2.5 h-2.5 text-[#B3B3B3]" />
                ) : (
                  <ChevronDown className="w-2.5 h-2.5 text-[#B3B3B3]" />
                )}
              </div>
            </div>
            <div className="h-[320px] overflow-y-auto">
              {filteredModels.length > 0 ? (
                filteredModels.map((endpoint) => (
                  <ModelListCard
                    key={endpoint.id}
                    data={endpoint}
                    handleClick={() => handleSelectModel(endpoint)}
                  />
                ))
              ) : (
                <Empty
                  description={
                    <span className="text-[#808080] text-xs">
                      {searchValue
                        ? `No models found matching "${searchValue}"`
                        : "No available models"}
                    </span>
                  }
                  className="py-8"
                />
              )}
            </div>
          </div>
        </div>
      </BlurModal>

      {/* Load Model Button */}
      <div ref={buttonRef}>
        {session?.selectedDeployment ? (
          <Button
            type="default"
            className="w-[12.25rem] 2rem border-[1px] border-[#1F1F1F]"
            onClick={() => setOpen(!open)}
          >
            <Image
              src={typeof session.selectedDeployment.model === 'string'
                ? "/icons/modelRepoWhite.png"
                : session.selectedDeployment.model?.provider?.icon || "/icons/modelRepoWhite.png"}
              fallback="/icons/modelRepoWhite.png"
              preview={false}
              alt="model"
              style={{
                width: ".875rem",
                height: ".875rem",
              }}
            />
            <Text_12_400_EEEEEE className="Open-Sans">{session.selectedDeployment.name}</Text_12_400_EEEEEE>
          </Button>
        ) : (
          <Button
            type="primary"
            className=" w-[12.25rem] 2rem"
            onClick={() => setOpen(!open)}
          >
            <Text_12_400_EEEEEE className="Open-Sans">Load Model</Text_12_400_EEEEEE>
          </Button>
        )}
      </div>
    </div>
  );
}
