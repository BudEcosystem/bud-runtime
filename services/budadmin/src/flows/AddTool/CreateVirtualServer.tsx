import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useAddTool } from "@/stores/useAddTool";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";

export default function CreateVirtualServer() {
  const { closeDrawer, openDrawerWithStep } = useDrawer();

  const {
    createdTools,
    selectedToolIds,
    virtualServerName,
    virtualServerId,
    isLoading,
    error,
    setVirtualServerName,
    createVirtualServer,
  } = useAddTool();

  const [isCreated, setIsCreated] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const selectedToolsCount = selectedToolIds.length;
  const selectedTools = createdTools.filter((t) => selectedToolIds.includes(t.id));

  const handleNext = async () => {
    if (isCreated) {
      closeDrawer();
      return;
    }

    setCreateError(null);
    try {
      const result = await createVirtualServer();
      if (result) {
        setIsCreated(true);
      } else {
        setCreateError(error || "Failed to create virtual server");
      }
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create virtual server");
    }
  };

  const handleBack = () => {
    openDrawerWithStep("tool-creation-success");
  };

  const isNextDisabled = !isCreated && (!virtualServerName.trim() || selectedToolsCount === 0 || isLoading);

  if (isCreated) {
    return (
      <BudForm
        data={{}}
        nextText="Done"
        onNext={handleNext}
      >
        <BudWraperBox>
          <BudDrawerLayout>
            <BudStepAlert
              type="success"
              title="Virtual Server Created"
              description={`Your virtual server "${virtualServerName}" has been created with ${selectedToolsCount} tool${selectedToolsCount !== 1 ? "s" : ""}.`}
            />
          </BudDrawerLayout>

          <BudDrawerLayout>
            <div className="px-[1.4rem] py-4">
              <div className="border border-[#3F3F3F] rounded-lg p-4 bg-[#0F0F0F]">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg bg-[#965CDE]/20 flex items-center justify-center">
                    <span className="text-xl">🖥️</span>
                  </div>
                  <div>
                    <Text_14_400_EEEEEE>{virtualServerName}</Text_14_400_EEEEEE>
                    <Text_12_400_B3B3B3>Virtual MCP Server</Text_12_400_B3B3B3>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Text_12_400_B3B3B3>Tools Included</Text_12_400_B3B3B3>
                    <Text_12_400_B3B3B3>{selectedToolsCount}</Text_12_400_B3B3B3>
                  </div>
                  <div className="flex justify-between">
                    <Text_12_400_B3B3B3>Status</Text_12_400_B3B3B3>
                    <span className="text-green-400 text-[0.75rem]">Active</span>
                  </div>
                </div>
              </div>
            </div>
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  return (
    <BudForm
      data={{}}
      nextText={isLoading ? "Creating..." : "Create Virtual Server"}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      disableNext={isNextDisabled}
      drawerLoading={isLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Virtual Server"
            description="Group your tools into a virtual MCP server for easier management"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          {/* Error Message */}
          {createError && (
            <div className="px-[1.4rem] py-2">
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <Text_12_400_B3B3B3 className="text-red-400">
                  {createError}
                </Text_12_400_B3B3B3>
              </div>
            </div>
          )}

          {/* Server Name Input */}
          <div className="px-[1.4rem] py-4">
            <Text_14_400_EEEEEE className="mb-2">Server Name</Text_14_400_EEEEEE>
            <input
              type="text"
              placeholder="Enter virtual server name"
              value={virtualServerName}
              onChange={(e) => setVirtualServerName(e.target.value)}
              className="w-full bg-transparent border border-[#3F3F3F] rounded-[6px] px-3 py-2 text-[#EEEEEE] text-[0.875rem] placeholder-[#757575] focus:outline-none focus:border-[#757575]"
            />
            <Text_12_400_B3B3B3 className="mt-2">
              This name will be used to identify your virtual server
            </Text_12_400_B3B3B3>
          </div>

          {/* Selected Tools Summary */}
          <div className="px-[1.4rem] py-4 border-t border-[#1F1F1F]">
            <div className="flex items-center justify-between mb-3">
              <Text_14_400_EEEEEE>Selected Tools</Text_14_400_EEEEEE>
              <span className="px-2 py-1 text-[0.625rem] rounded bg-[#965CDE]/20 text-[#965CDE]">
                {selectedToolsCount} tool{selectedToolsCount !== 1 ? "s" : ""}
              </span>
            </div>

            <div className="max-h-[200px] overflow-y-auto space-y-2">
              {selectedTools.map((tool) => (
                <div
                  key={tool.id}
                  className="flex items-center gap-2 p-2 bg-[#1F1F1F]/50 rounded"
                >
                  <span className="text-sm">{tool.icon || "🔧"}</span>
                  <Text_12_400_B3B3B3 className="truncate flex-1">
                    {tool.name}
                  </Text_12_400_B3B3B3>
                </div>
              ))}
            </div>
          </div>

          {/* Info */}
          <div className="px-[1.4rem] py-4 border-t border-[#1F1F1F]">
            <div className="bg-[#1F1F1F]/50 rounded-lg p-3">
              <Text_12_400_B3B3B3 className="leading-relaxed">
                A virtual server bundles multiple tools into a single MCP-compatible endpoint.
                This makes it easier to manage and deploy related tools together.
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
