import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState, useContext, useCallback, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useAddTool, CatalogueServer } from "@/stores/useAddTool";
import { Spin } from "antd";
import { Text_12_400_B3B3B3 } from "@/components/ui/text";

interface CatalogueServerDisplay {
  id: string;
  name: string;
  description: string;
  icon: string;
  iconLocal: boolean;
  status: "active" | "inactive";
  toolsCount?: number;
}

export default function BudToolsCatalogue() {
  const { openDrawerWithStep, openDrawerWithExpandedStep } = useDrawer();
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const [searchTerm, setSearchTerm] = useState<string>("");

  const {
    catalogueServers,
    selectedCatalogueServerIds,
    isLoading,
    error,
    fetchCatalogueServers,
    toggleCatalogueServer,
    updateWorkflowStep,
  } = useAddTool();

  // Fetch catalogue servers on mount
  useEffect(() => {
    fetchCatalogueServers();
  }, [fetchCatalogueServers]);

  // Transform catalogue servers to display format
  const displayServers: CatalogueServerDisplay[] = catalogueServers.map((server) => ({
    id: server.id,
    name: server.name,
    description: server.description || "MCP Server from Bud Catalogue",
    icon: server.icon || "/images/drawer/brain.png",
    iconLocal: !server.icon,
    status: "active" as const,
    toolsCount: server.toolsCount,
  }));

  // Filter servers based on search
  const filteredServers = displayServers.filter(
    (server) =>
      server.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      server.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Callback to update selected servers from expanded view
  const handleServersSelected = useCallback((serverId: string, subToolIds: string[]) => {
    toggleCatalogueServer(serverId);
  }, [toggleCatalogueServer]);

  const handleServerClick = (server: CatalogueServerDisplay) => {
    // Toggle selection for now, can open expanded view later if needed
    toggleCatalogueServer(server.id);
  };

  const handleNext = async () => {
    try {
      // Update workflow with selected catalogue servers
      // Catalogue flow skips progress step, goes directly to success
      const result = await updateWorkflowStep(2, true);
      if (result) {
        openDrawerWithStep("tool-creation-success");
      }
    } catch (error) {
      console.error("Failed to register catalogue servers:", error);
    }
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
      disableNext={selectedCatalogueServerIds.length === 0 || isExpandedViewOpen || isLoading}
      drawerLoading={isLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Bud Tools Catalogue"
            description="Select MCP servers from Bud's repository of 1000+ pre-built tools"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          {/* Search Section */}
          <div className="px-[1.4rem] py-[1rem] border-b border-[#1F1F1F]">
            <div className="flex items-center gap-2">
              <div className="flex-1 relative">
                <input
                  type="text"
                  placeholder="Search servers..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full bg-transparent border border-[#3F3F3F] rounded-[6px] px-3 py-2 text-[#EEEEEE] text-[0.875rem] placeholder-[#757575] focus:outline-none focus:border-[#757575]"
                />
                <svg
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#757575]"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="M21 21l-4.35-4.35" />
                </svg>
              </div>
              <button className="p-2 border border-[#3F3F3F] rounded-[6px] hover:border-[#757575] transition-all">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 15 15"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="text-[#B3B3B3]"
                >
                  <path
                    fillRule="evenodd"
                    clipRule="evenodd"
                    d="M5.5 3C4.67157 3 4 3.67157 4 4.5C4 5.32843 4.67157 6 5.5 6C6.32843 6 7 5.32843 7 4.5C7 3.67157 6.32843 3 5.5 3ZM3 5C3.01671 5 3.03323 4.99918 3.04952 4.99758C3.28022 6.1399 4.28967 7 5.5 7C6.71033 7 7.71978 6.1399 7.95048 4.99758C7.96677 4.99918 7.98329 5 8 5H13.5C13.7761 5 14 4.77614 14 4.5C14 4.22386 13.7761 4 13.5 4H8C7.98329 4 7.96677 4.00082 7.95048 4.00242C7.71978 2.86009 6.71033 2 5.5 2C4.28967 2 3.28022 2.86009 3.04952 4.00242C3.03323 4.00082 3.01671 4 3 4H1.5C1.22386 4 1 4.22386 1 4.5C1 4.77614 1.22386 5 1.5 5H3ZM11.9505 10.9976C11.7198 12.1399 10.7103 13 9.5 13C8.28967 13 7.28022 12.1399 7.04952 10.9976C7.03323 10.9992 7.01671 11 7 11H1.5C1.22386 11 1 10.7761 1 10.5C1 10.2239 1.22386 10 1.5 10H7C7.01671 10 7.03323 10.0008 7.04952 10.0024C7.28022 8.8601 8.28967 8 9.5 8C10.7103 8 11.7198 8.8601 11.9505 10.0024C11.9668 10.0008 11.9833 10 12 10H13.5C13.7761 10 14 10.2239 14 10.5C14 10.7761 13.7761 11 13.5 11H12C11.9833 11 11.9668 10.9992 11.9505 10.9976ZM8 10.5C8 9.67157 8.67157 9 9.5 9C10.3284 9 11 9.67157 11 10.5C11 11.3284 10.3284 12 9.5 12C8.67157 12 8 11.3284 8 10.5Z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>

          {/* Servers List */}
          <div className="max-h-[400px] overflow-y-auto">
            {isLoading && catalogueServers.length === 0 ? (
              <div className="flex justify-center items-center py-8">
                <Spin size="default" />
              </div>
            ) : error ? (
              <div className="px-[1.4rem] py-4">
                <Text_12_400_B3B3B3 className="text-red-400">
                  Failed to load catalogue: {error}
                </Text_12_400_B3B3B3>
              </div>
            ) : filteredServers.length === 0 ? (
              <div className="px-[1.4rem] py-4">
                <Text_12_400_B3B3B3>
                  {searchTerm ? "No servers match your search" : "No servers available"}
                </Text_12_400_B3B3B3>
              </div>
            ) : (
              filteredServers.map((server) => (
                <ProviderCardWithCheckBox
                  key={server.id}
                  data={server}
                  selected={selectedCatalogueServerIds.includes(server.id)}
                  handleClick={() => handleServerClick(server)}
                />
              ))
            )}
          </div>

          {/* Selection Summary */}
          {selectedCatalogueServerIds.length > 0 && (
            <div className="px-[1.4rem] py-2 border-t border-[#1F1F1F]">
              <Text_12_400_B3B3B3>
                {selectedCatalogueServerIds.length} server{selectedCatalogueServerIds.length > 1 ? "s" : ""} selected
              </Text_12_400_B3B3B3>
            </div>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
