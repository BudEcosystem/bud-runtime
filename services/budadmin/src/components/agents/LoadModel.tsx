import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Button, Image, Empty, Spin } from "antd";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useAgentStore } from "@/stores/useAgentStore";
import { useAddAgent } from "@/stores/useAddAgent";
import BlurModal from "./BlurModal";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl, assetBaseUrl } from "@/components/environment";
import { errorToast } from "@/components/toast";
import { ModelListCard } from "../ui/bud/deploymentDrawer/ModelListCard";
import { Model } from "src/hooks/useModels";

interface LoadModelProps {
  sessionId: string;
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

interface ModelWrapper {
  id: string;           // endpoint/deployment ID
  name: string;         // deployment name (e.g., 'gpt-4-mini')
  model: Model;         // nested model data (model.name is the model name, e.g., 'gpt-4.1-mini')
  [key: string]: any;
}

const DEFAULT_MODEL_ICON = "/icons/modelRepoWhite.png";
const CLOUD_PROVIDER_TYPES = ["hugging_face", "cloud_model"];

export default function LoadModel({ sessionId, open, setOpen }: LoadModelProps) {
  const { updateSession, sessions } = useAgentStore();
  const { selectedProject } = useAddAgent();
  const session = sessions.find(s => s.id === sessionId);

  const modelIconUrl = useMemo(() => {
    const model = session?.selectedDeployment?.model;
    if (!model) {
      return DEFAULT_MODEL_ICON;
    }
    if (model.icon) {
      return assetBaseUrl + model.icon;
    }
    if (CLOUD_PROVIDER_TYPES.includes(model.provider_type) && model.provider?.icon) {
      return assetBaseUrl + model.provider.icon;
    }
    return DEFAULT_MODEL_ICON;
  }, [session?.selectedDeployment?.model]);

  const [sortBy] = useState("recency");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [currentlyLoaded, setCurrentlyLoaded] = useState<ModelWrapper[]>([]);
  const [availableModels, setAvailableModels] = useState<ModelWrapper[]>([]);
  const [searchValue, setSearchValue] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalModels, setTotalModels] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const pageSize = 10;

  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout>();

  // Fetch models from API
  const fetchModels = useCallback(async (page: number, search?: string, isLoadMore: boolean = false) => {
    if (isLoadMore) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }

    try {
      const params: any = {
        page,
        limit: pageSize,
        search: Boolean(search)
      };

      // Add search parameter if exists
      if (search) {
        params.name = search;
      }

      // Add project_id filter if selected project exists
      if (selectedProject?.id) {
        params.project_id = selectedProject.id;
      }

      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/playground/deployments`, {
        params
      });

      if (response?.data) {
        const endpoints = response.data.endpoints || [];
        setTotalPages(response.data.total_pages || 1);
        setTotalModels(response.data.total_record || 0);

        if (isLoadMore) {
          // Append to existing models
          setAvailableModels(prev => [...prev, ...endpoints]);
        } else {
          // Replace models
          setAvailableModels(endpoints);
        }

        // Set currently loaded model if it exists
        if (session?.selectedDeployment?.id) {
          const current = endpoints.find(
            (endpoint: ModelWrapper) => endpoint.model?.id === session.selectedDeployment?.id || endpoint.id === session.selectedDeployment?.id
          );
          if (current) {
            setCurrentlyLoaded([current]);
            // Remove from available models
            setAvailableModels(prev =>
              prev.filter((endpoint: ModelWrapper) => {
                const modelId = endpoint.model?.id || endpoint.id;
                return modelId !== session.selectedDeployment?.id;
              })
            );
          }
        }
      }
    } catch (error) {
      console.error("Error fetching deployments:", error);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [session?.selectedDeployment?.id, sortOrder, pageSize, selectedProject?.id]);

  // Initial load when modal opens
  useEffect(() => {
    if (open) {
      setCurrentPage(1);
      fetchModels(1, searchValue, false);

      // If there's already a selected deployment, ensure it's in currentlyLoaded
      // Don't set it here as fetchModels will find and set it from the API response
    }
  }, [open, sortOrder, fetchModels]);

  // Handle search with debounce
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(() => {
      if (open) {
        setCurrentPage(1);
        fetchModels(1, searchValue, false);
      }
    }, 500);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchValue, fetchModels, open]);

  // Handle scroll for lazy loading
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const element = e.currentTarget;
    const { scrollTop, scrollHeight, clientHeight } = element;

    // Check if scrolled to bottom
    if (scrollHeight - scrollTop <= clientHeight + 50 &&
        !isLoadingMore &&
        currentPage < totalPages) {
      setCurrentPage(prev => prev + 1);
      fetchModels(currentPage + 1, searchValue, true);
    }
  }, [currentPage, totalPages, isLoadingMore, searchValue, fetchModels]);

  const handleSelectModel = async (endpoint: ModelWrapper) => {
    // endpoint.name is the deployment name (e.g., 'gpt-4-mini')
    // endpoint.model.name is the model name (e.g., 'gpt-4.1-mini')
    const deploymentName = endpoint.name;
    const modelData = endpoint.model;
    const endpointId = endpoint.id;

    try {
      // Call the prompt-config API with the deployment name and prompt_id
      const payload = {
        prompt_id: session?.promptId,
        deployment_name: deploymentName,
        stream: session?.settings?.stream ?? false
      };

      await AppRequest.Post(`${tempApiBaseUrl}/prompts/prompt-config`, payload);
    } catch (error) {
      console.error("Error calling prompt-config API:", error);
      errorToast("Failed to configure prompt for selected deployment");
    }

    updateSession(sessionId, {
      modelId: modelData.id,
      modelName: modelData.name,
      selectedDeployment: {
        id: endpointId, // Store endpoint ID, not model ID
        name: deploymentName, // Use deployment name, not model name
        model: {
          name: modelData.name, // Store model name separately
          icon: modelData.icon,
          provider: modelData.provider,
          provider_type: modelData.provider_type
        }
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
                {currentlyLoaded.map((model) => (
                  <ModelListCard
                    key={model.model.id}
                    data={model.model}
                    hideSeeMore={true}
                    selected={true}
                    handleClick={() => handleSelectModel(model)}
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
                  {totalModels}
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
            <div
              className="h-[320px] overflow-y-auto"
              onScroll={handleScroll}
              ref={scrollContainerRef}
            >
              {isLoading && availableModels.length === 0 ? (
                <div className="flex justify-center items-center h-full">
                  <Spin size="default" />
                </div>
              ) : availableModels.length > 0 ? (
                <>
                  {availableModels.map((model) => (
                    <ModelListCard
                      key={model.model.id}
                      data={model.model}
                      hideSeeMore={true}
                      handleClick={() => handleSelectModel(model)}
                    />
                  ))}
                  {isLoadingMore && (
                    <div className="flex justify-center py-4">
                      <Spin size="small" />
                    </div>
                  )}
                </>
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
            className="w-[12.25rem] h-[2rem] border-[1px] border-[#1F1F1F] bg-transparent hover:bg-[#1A1A1A] flex items-center justify-center gap-2"
            onClick={() => setOpen(!open)}
            style={{
              backgroundColor: 'transparent',
              color: '#EEEEEE'
            }}
          >
            <Image
              src={modelIconUrl}
              fallback={DEFAULT_MODEL_ICON}
              preview={false}
              alt="model"
              style={{
                width: ".875rem",
                height: ".875rem",
              }}
            />
            <span className="text-[#EEEEEE] text-xs Open-Sans">{session.selectedDeployment.name}</span>
          </Button>
        ) : (
          <Button
            type="default"
            className="w-[12.25rem] h-[2rem] border-[1px] border-[#1F1F1F] bg-transparent hover:bg-[#1A1A1A] flex items-center justify-center gap-2"
            onClick={() => setOpen(!open)}
            style={{
              backgroundColor: 'transparent',
              color: '#FFFFFF'
            }}
          >
            <span className="text-white text-xs Open-Sans">Load Model</span>
          </Button>
        )}
      </div>
    </div>
  );
}
