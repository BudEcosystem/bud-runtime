import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState, useMemo } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Switch, message } from "antd";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import DragDropUpload from "@/components/ui/DragDropUpload";
import { useAddTool, ToolSourceType } from "@/stores/useAddTool";

type TabType = "openapi-file" | "openapi-url" | "api-docs-file" | "api-docs-url";

// Check if initial source type from step 1 is documentation-based
const isDocumentationSource = (sourceType: ToolSourceType | null): boolean => {
  return sourceType === ToolSourceType.API_DOCS_URL || sourceType === ToolSourceType.API_DOCS_FILE;
};

// Check if initial source type from step 1 is OpenAPI-based
const isOpenAPISource = (sourceType: ToolSourceType | null): boolean => {
  return sourceType === ToolSourceType.OPENAPI_URL || sourceType === ToolSourceType.OPENAPI_FILE;
};

export default function OpenAPISpecification() {
  const { openDrawerWithStep } = useDrawer();

  const {
    sourceType,
    openApiUrl,
    apiDocsUrl,
    enhanceWithAi,
    uploadedFile,
    isLoading,
    error,
    setSourceType,
    setOpenApiUrl,
    setApiDocsUrl,
    setEnhanceWithAi,
    setUploadedFile,
    updateWorkflowStep,
    uploadFileAndCreate,
  } = useAddTool();

  // Determine which mode we're in based on step 1 selection
  const isDocMode = isDocumentationSource(sourceType);
  const isOpenAPIMode = isOpenAPISource(sourceType);

  // Get available tabs based on step 1 selection
  const availableTabs = useMemo(() => {
    if (isDocMode) {
      return [
        { id: "api-docs-file" as TabType, label: "API Docs File" },
        { id: "api-docs-url" as TabType, label: "API Docs URL" },
      ];
    }
    // Default: OpenAPI mode
    return [
      { id: "openapi-file" as TabType, label: "OpenAPI File" },
      { id: "openapi-url" as TabType, label: "OpenAPI URL" },
    ];
  }, [isDocMode]);

  // Initialize active tab based on source type
  const initialTab = useMemo((): TabType => {
    if (isDocMode) {
      return sourceType === ToolSourceType.API_DOCS_FILE ? "api-docs-file" : "api-docs-url";
    }
    return sourceType === ToolSourceType.OPENAPI_FILE ? "openapi-file" : "openapi-url";
  }, [sourceType, isDocMode]);

  const [activeTab, setActiveTab] = useState<TabType>(initialTab);

  // Handle tab change - just updates local tab state, doesn't trigger API
  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
  };

  const handleFileSelect = (file: File) => {
    setUploadedFile(file);
  };

  const isNextDisabled = () => {
    if (isLoading) return true;

    switch (activeTab) {
      case "openapi-file":
      case "api-docs-file":
        return !uploadedFile;
      case "openapi-url":
        return !openApiUrl.trim();
      case "api-docs-url":
        return !apiDocsUrl.trim();
      default:
        return true;
    }
  };

  const handleNext = async () => {
    try {
      let result;

      if (activeTab === "openapi-file") {
        // OpenAPI File upload flow
        setSourceType(ToolSourceType.OPENAPI_FILE);
        result = await uploadFileAndCreate();
      } else if (activeTab === "openapi-url") {
        // OpenAPI URL flow
        setSourceType(ToolSourceType.OPENAPI_URL);
        result = await updateWorkflowStep(2, true);
      } else if (activeTab === "api-docs-file") {
        // API Docs File upload flow
        setSourceType(ToolSourceType.API_DOCS_FILE);
        result = await uploadFileAndCreate();
      } else if (activeTab === "api-docs-url") {
        // API Docs URL flow
        setSourceType(ToolSourceType.API_DOCS_URL);
        result = await updateWorkflowStep(2, true);
      }

      // Only navigate to next step if API call succeeded
      if (result) {
        openDrawerWithStep("creating-tool-status");
      }
    } catch (err: any) {
      console.error("Failed to start tool creation:", err);
      // Show error message to user
      const errorMessage = err?.response?.data?.message || err?.message || "Failed to start tool creation";
      message.error(errorMessage);
    }
  };

  const handleBack = () => {
    openDrawerWithStep("select-tool-source");
  };

  // Get title and description based on mode
  const getTitle = () => isDocMode ? "API Documentation" : "OpenAPI Specification";
  const getDescription = () => isDocMode
    ? "Create MCP compatible tools using API documentation. Provide a documentation file or URL."
    : "Create MCP compatible tools using OpenAPI Specification. Provide an OpenAPI 3.0+ file or URL.";

  return (
    <BudForm
      data={{}}
      nextText="Next"
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      disableNext={isNextDisabled()}
      drawerLoading={isLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={getTitle()}
            description={getDescription()}
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          {/* Tabs - dynamically generated based on step 1 selection */}
          <div className="px-[1.4rem] pt-[1.5rem]">
            <div className="flex border border-[#3F3F3F] rounded-[6px] overflow-hidden">
              {availableTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`flex-1 py-[0.6rem] px-[1rem] text-[0.75rem] transition-all ${
                    activeTab === tab.id
                      ? "bg-[#1F1F1F] text-[#EEEEEE] border-r border-[#3F3F3F]"
                      : "bg-transparent text-[#B3B3B3] hover:text-[#EEEEEE] border-r border-[#3F3F3F]"
                  } last:border-r-0`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tab Content */}
          <div className="px-[1.4rem] pt-[1.5rem]">
            {/* OpenAPI File Tab */}
            {activeTab === "openapi-file" && (
              <div>
                <DragDropUpload
                  onFileSelect={handleFileSelect}
                  accept=".json,.yaml,.yml"
                  title="Drag and drop your OpenAPI file here, or click to browse"
                  selectedFile={uploadedFile}
                />
              </div>
            )}

            {/* OpenAPI URL Tab */}
            {activeTab === "openapi-url" && (
              <div>
                <Text_14_400_EEEEEE className="mb-[0.5rem]">
                  OpenAPI Specification URL
                </Text_14_400_EEEEEE>
                <input
                  type="text"
                  placeholder="https://api.example.com/openapi.json"
                  value={openApiUrl}
                  onChange={(e) => setOpenApiUrl(e.target.value)}
                  className="w-full bg-transparent border border-[#3F3F3F] rounded-[6px] px-3 py-2 text-[#EEEEEE] text-[0.875rem] placeholder-[#757575] focus:outline-none focus:border-[#757575]"
                />
              </div>
            )}

            {/* API Docs File Tab */}
            {activeTab === "api-docs-file" && (
              <div>
                <DragDropUpload
                  onFileSelect={handleFileSelect}
                  accept=".json,.yaml,.yml,.md,.txt"
                  title="Drag and drop your API documentation file here, or click to browse"
                  selectedFile={uploadedFile}
                />
              </div>
            )}

            {/* API Docs URL Tab */}
            {activeTab === "api-docs-url" && (
              <div>
                <Text_14_400_EEEEEE className="mb-[0.5rem]">
                  API Documentation URL
                </Text_14_400_EEEEEE>
                <input
                  type="text"
                  placeholder="https://docs.example.com/api"
                  value={apiDocsUrl}
                  onChange={(e) => setApiDocsUrl(e.target.value)}
                  className="w-full bg-transparent border border-[#3F3F3F] rounded-[6px] px-3 py-2 text-[#EEEEEE] text-[0.875rem] placeholder-[#757575] focus:outline-none focus:border-[#757575]"
                />
              </div>
            )}

            {/* Enhance with AI Toggle */}
            <div className="mt-[1.5rem]">
              <div className="flex items-center gap-[0.5rem]">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-[#B3B3B3]"
                >
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
                <Switch
                  checked={enhanceWithAi}
                  onChange={setEnhanceWithAi}
                  size="small"
                />
                <Text_14_400_EEEEEE>Enhance with AI</Text_14_400_EEEEEE>
              </div>
              <Text_12_400_B3B3B3 className="mt-[0.5rem] leading-[150%]">
                If enabled, we will automatically create better descriptions
                that enables better tool discovery
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
