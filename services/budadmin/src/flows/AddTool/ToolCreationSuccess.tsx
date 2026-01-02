import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useAddTool, ToolSourceType } from "@/stores/useAddTool";
import { Tool } from "@/stores/useTools";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import { Checkbox, Spin } from "antd";

interface ToolCardProps {
  tool: Tool;
  selected: boolean;
  onToggle: () => void;
}

function ToolCard({ tool, selected, onToggle }: ToolCardProps) {
  return (
    <div
      className={`flex items-center gap-3 px-[1.4rem] py-3 border-b border-[#1F1F1F] cursor-pointer hover:bg-[#1F1F1F]/50 transition-colors ${
        selected ? "bg-[#1F1F1F]/30" : ""
      }`}
      onClick={onToggle}
    >
      <Checkbox checked={selected} onChange={onToggle} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-lg">{tool.icon || "🔧"}</span>
          <Text_14_400_EEEEEE className="truncate">{tool.name}</Text_14_400_EEEEEE>
        </div>
        {tool.description && (
          <Text_12_400_B3B3B3 className="mt-1 line-clamp-2">
            {tool.description}
          </Text_12_400_B3B3B3>
        )}
      </div>
      {tool.category && (
        <span className="px-2 py-1 text-[0.625rem] rounded bg-[#965CDE]/20 text-[#965CDE]">
          {tool.category}
        </span>
      )}
    </div>
  );
}

export default function ToolCreationSuccess() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();

  const {
    createdTools,
    selectedToolIds,
    isLoading,
    error,
    sourceType,
    fetchCreatedTools,
    toggleToolSelection,
    selectAllTools,
    deselectAllTools,
  } = useAddTool();

  const isCatalogueFlow = sourceType === ToolSourceType.BUD_CATALOGUE;

  // Fetch created tools on mount
  useEffect(() => {
    fetchCreatedTools();
  }, [fetchCreatedTools]);

  const handleToggleAll = () => {
    if (selectedToolIds.length === createdTools.length) {
      deselectAllTools();
    } else {
      selectAllTools();
    }
  };

  const handleSkip = () => {
    closeDrawer();
  };

  const handleCreateVirtualServer = () => {
    openDrawerWithStep("create-virtual-server");
  };

  const allSelected = selectedToolIds.length === createdTools.length && createdTools.length > 0;

  // Get alert content based on flow type
  const alertTitle = isCatalogueFlow ? "Tools Added Successfully" : "Tools Created Successfully";
  const alertDescription = isCatalogueFlow
    ? `${createdTools.length} tool${createdTools.length !== 1 ? "s" : ""} have been added from the catalogue.`
    : `${createdTools.length} tool${createdTools.length !== 1 ? "s" : ""} have been created and are ready to use.`;

  return (
    <BudForm
      data={{}}
      nextText={`Create Virtual Server (${selectedToolIds.length})`}
      onNext={handleCreateVirtualServer}
      backText="Skip"
      onBack={handleSkip}
      disableNext={selectedToolIds.length === 0}
      drawerLoading={isLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <BudStepAlert
            type="success"
            title={alertTitle}
            description={alertDescription}
          />
        </BudDrawerLayout>

        <BudDrawerLayout>
          <DrawerTitleCard
            title={isCatalogueFlow ? "Added Tools" : "Created Tools"}
            description={isCatalogueFlow
              ? "Review the tools added from the catalogue"
              : "Review the tools that were created from your specification"}
            classNames="pt-[.4rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          {/* Select All / Deselect All */}
          <div className="px-[1.4rem] py-2 border-b border-[#1F1F1F] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Checkbox
                checked={allSelected}
                indeterminate={selectedToolIds.length > 0 && selectedToolIds.length < createdTools.length}
                onChange={handleToggleAll}
              />
              <Text_12_400_B3B3B3>
                {allSelected ? "Deselect All" : "Select All"}
              </Text_12_400_B3B3B3>
            </div>
            <Text_12_400_B3B3B3>
              {selectedToolIds.length} of {createdTools.length} selected
            </Text_12_400_B3B3B3>
          </div>

          {/* Tools List */}
          <div className="max-h-[300px] overflow-y-auto">
            {isLoading && createdTools.length === 0 ? (
              <div className="flex justify-center items-center py-8">
                <Spin size="default" />
              </div>
            ) : error ? (
              <div className="px-[1.4rem] py-4">
                <Text_12_400_B3B3B3 className="text-red-400">
                  Failed to load tools: {error}
                </Text_12_400_B3B3B3>
              </div>
            ) : createdTools.length === 0 ? (
              <div className="px-[1.4rem] py-4">
                <Text_12_400_B3B3B3>No tools were created</Text_12_400_B3B3B3>
              </div>
            ) : (
              createdTools.map((tool) => (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  selected={selectedToolIds.includes(tool.id)}
                  onToggle={() => toggleToolSelection(tool.id)}
                />
              ))
            )}
          </div>
        </BudDrawerLayout>

      </BudWraperBox>
    </BudForm>
  );
}
