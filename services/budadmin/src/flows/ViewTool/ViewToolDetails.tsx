import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_B3B3B3,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import React, { useState } from "react";
import { Checkbox } from "antd";
import ProjectTags from "src/flows/components/ProjectTags";
import { useTools } from "src/stores/useTools";

interface SubTool {
  id: string;
  name: string;
  description: string;
}

export default function ViewToolDetails() {
  const { selectedTool } = useTools();
  const [selectedSubTools, setSelectedSubTools] = useState<Set<string>>(
    new Set()
  );

  // Use sub-tools from selectedTool if available
  // Note: Sub-tools data should be fetched from the MCP Foundry API via the tool details endpoint
  const subTools: SubTool[] = selectedTool?.subTools || [];

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedSubTools(new Set(subTools.map((t) => t.id)));
    } else {
      setSelectedSubTools(new Set());
    }
  };

  const handleSubToolSelect = (id: string, checked: boolean) => {
    setSelectedSubTools((prev) => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(id);
      } else {
        newSet.delete(id);
      }
      return newSet;
    });
  };

  const isAllSelected =
    subTools.length > 0 && selectedSubTools.size === subTools.length;

  const handleDeploy = () => {
    console.log("Deploy clicked with selected tools:", Array.from(selectedSubTools));
    // TODO: Implement deploy functionality
  };

  return (
    <BudForm
      data={{}}
      nextText="Deploy"
      onNext={handleDeploy}
      disableNext={selectedSubTools.size === 0}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          {/* Header Section */}
          <div className="flex items-start justify-between w-full p-[1.35rem] border-b border-[#1F1F1F]">
            <div className="flex items-start justify-start max-w-[90%]">
              <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
                <div className="w-[1.75rem] h-[1.75rem] text-[1.5rem] flex items-center justify-center">
                  {selectedTool?.icon || "🔧"}
                </div>
              </div>
              <div>
                <Text_14_400_EEEEEE className="mb-[0.65rem] leading-[140%]">
                  {selectedTool?.name || "Tool Name"}
                </Text_14_400_EEEEEE>
                <div className="flex items-center gap-[.35rem] flex-wrap mb-[0.65rem]">
                  {selectedTool?.tags?.map((tag, index) => (
                    <ProjectTags
                      key={index}
                      name={tag.name}
                      color={tag.color}
                    />
                  )) || (
                    <>
                      <ProjectTags name="Tag 1" color="#965CDE" />
                      <ProjectTags name="Tag 2" color="#22C55E" />
                      <ProjectTags name="tool" color="#3B82F6" />
                    </>
                  )}
                </div>
                <Text_13_400_B3B3B3 className="leading-[150%]">
                  {selectedTool?.description ||
                    "Description Description Description"}
                </Text_13_400_B3B3B3>
              </div>
            </div>
          </div>

          {/* Available Tools Section */}
          <div className="p-[1.35rem]">
            <div className="flex items-center justify-between mb-[1rem]">
              <Text_17_600_FFFFFF>
                Available Tools ({subTools.length})
              </Text_17_600_FFFFFF>
            </div>

            {subTools.length > 0 ? (
              <>
                {/* Select All */}
                <div className="flex items-center gap-[0.75rem] py-[0.75rem] border-b border-[#1F1F1F]">
                  <Checkbox
                    checked={isAllSelected}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                  />
                  <Text_14_400_EEEEEE>Select All</Text_14_400_EEEEEE>
                </div>

                {/* Sub Tools List */}
                <div className="max-h-[400px] overflow-y-auto">
                  {subTools.map((subTool) => (
                    <div
                      key={subTool.id}
                      className="flex items-start gap-[0.75rem] py-[1rem] border-b border-[#1F1F1F] cursor-pointer hover:bg-[#1F1F1F]/30 px-[0.25rem] -mx-[0.25rem] rounded"
                      onClick={() =>
                        handleSubToolSelect(
                          subTool.id,
                          !selectedSubTools.has(subTool.id)
                        )
                      }
                    >
                      <Checkbox
                        checked={selectedSubTools.has(subTool.id)}
                        onChange={(e) => {
                          e.stopPropagation();
                          handleSubToolSelect(subTool.id, e.target.checked);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="mt-[2px]"
                      />
                      <div className="flex-1">
                        <Text_14_400_EEEEEE className="mb-[0.35rem]">
                          {subTool.name}
                        </Text_14_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="leading-[150%]">
                          {subTool.description}
                        </Text_12_400_B3B3B3>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="py-[2rem] text-center border border-[#1F1F1F] rounded-[6px]">
                <Text_12_400_B3B3B3>
                  No sub-tools available for this tool.
                </Text_12_400_B3B3B3>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
