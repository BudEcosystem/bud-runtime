import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Switch } from "antd";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import DragDropUpload from "@/components/ui/DragDropUpload";

type TabType = "openapi-file" | "openapi-url" | "api-docs";

const tabs: { id: TabType; label: string }[] = [
  { id: "openapi-file", label: "OpenAPI File" },
  { id: "openapi-url", label: "OpenAPI URL" },
  { id: "api-docs", label: "API Docs" },
];

export default function OpenAPISpecification() {
  const { openDrawerWithStep } = useDrawer();
  const [activeTab, setActiveTab] = useState<TabType>("openapi-file");
  const [enhanceWithAI, setEnhanceWithAI] = useState(true);
  const [openAPIUrl, setOpenAPIUrl] = useState("");
  const [apiDocsUrl, setApiDocsUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [apiDocsFile, setApiDocsFile] = useState<File | null>(null);

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
  };

  const handleApiDocsFileSelect = (file: File) => {
    setApiDocsFile(file);
  };

  const isNextDisabled = () => {
    switch (activeTab) {
      case "openapi-file":
        return !selectedFile;
      case "openapi-url":
        return !openAPIUrl.trim();
      case "api-docs":
        return !apiDocsFile && !apiDocsUrl.trim();
      default:
        return true;
    }
  };

  const handleNext = () => {
    console.log("Active tab:", activeTab);
    console.log("Enhance with AI:", enhanceWithAI);
    if (activeTab === "openapi-file") {
      console.log("Selected file:", selectedFile);
    } else if (activeTab === "openapi-url") {
      console.log("OpenAPI URL:", openAPIUrl);
    } else {
      console.log("API Docs file:", apiDocsFile);
      console.log("API Docs URL:", apiDocsUrl);
    }
    openDrawerWithStep("creating-tool-status");
  };

  const handleBack = () => {
    openDrawerWithStep("select-tool-source");
  };

  return (
    <BudForm
      data={{}}
      nextText="Next"
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      disableNext={isNextDisabled()}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Open API Specification"
            description="Create MCP compatible tools using Open API Specification. You will be required to copy and paste Open API spec or Swagger."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          {/* Tabs */}
          <div className="px-[1.4rem] pt-[1.5rem]">
            <div className="flex border border-[#3F3F3F] rounded-[6px] overflow-hidden">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
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
                  value={openAPIUrl}
                  onChange={(e) => setOpenAPIUrl(e.target.value)}
                  className="w-full bg-transparent border border-[#3F3F3F] rounded-[6px] px-3 py-2 text-[#EEEEEE] text-[0.875rem] placeholder-[#757575] focus:outline-none focus:border-[#757575]"
                />
              </div>
            )}

            {/* API Docs Tab */}
            {activeTab === "api-docs" && (
              <div>
                <DragDropUpload
                  onFileSelect={handleApiDocsFileSelect}
                  accept=".json,.yaml,.yml,.md,.txt"
                  title="Drag and drop your OpenAPI file here, or click to browse"
                />

                {/* OR Divider */}
                <div className="flex items-center my-[1.5rem]">
                  <div className="flex-1 border-t border-[#3F3F3F]"></div>
                  <Text_12_400_B3B3B3 className="px-4">OR</Text_12_400_B3B3B3>
                  <div className="flex-1 border-t border-[#3F3F3F]"></div>
                </div>

                {/* API Docs URL */}
                <Text_14_400_EEEEEE className="mb-[0.5rem]">
                  API Docs URL
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
                  checked={enhanceWithAI}
                  onChange={setEnhanceWithAI}
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
