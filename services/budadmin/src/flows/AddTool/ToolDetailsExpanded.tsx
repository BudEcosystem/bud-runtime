import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Checkbox } from "antd";

interface SubTool {
  id: string;
  name: string;
  description: string;
}

interface ToolData {
  id: string;
  name: string;
  description: string;
  icon: string;
  subTools?: SubTool[];
}

interface ExpandedToolProps {
  tool: ToolData;
  onToolsSelected?: (toolId: string, subToolIds: string[]) => void;
}

export default function ToolDetailsExpanded() {
  const { expandedDrawerProps, closeExpandedStep } = useDrawer();
  const props = expandedDrawerProps as ExpandedToolProps;
  const [selectedSubTools, setSelectedSubTools] = useState<Set<string>>(
    new Set()
  );

  // Use sub-tools from the tool prop if available
  // Note: Sub-tools data should be fetched from the MCP Foundry API via the tool details endpoint
  const subTools: SubTool[] = props?.tool?.subTools || [];

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

  const handleClose = () => {
    // Notify parent about selected sub-tools before closing
    if (props?.onToolsSelected && props?.tool?.id) {
      props.onToolsSelected(props.tool.id, Array.from(selectedSubTools));
    }
    closeExpandedStep();
  };

  return (
    <BudForm data={{}} nextText="Close" onNext={handleClose}>
      <BudWraperBox>
        <BudDrawerLayout>
          {/* Header Section */}
          <div className="flex items-start gap-[1rem] p-[1.35rem] border-b border-[#1F1F1F]">
            <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] shrink-0 grow-0 flex items-center justify-center">
              <img
                src={props?.tool?.icon || "/images/drawer/brain.png"}
                alt={props?.tool?.name || "Tool"}
                className="w-[1.75rem] h-[1.75rem] object-contain"
              />
            </div>
            <div className="flex-1">
              <Text_17_600_FFFFFF className="mb-[0.5rem]">
                {props?.tool?.name || "Tool Name"}
              </Text_17_600_FFFFFF>
              <Text_12_400_B3B3B3 className="leading-[150%]">
                {props?.tool?.description || "Description Description Description"}
              </Text_12_400_B3B3B3>
            </div>
          </div>

          {/* Available Tools Section */}
          <div className="p-[1.35rem]">
            <div className="border border-[#1F1F1F] rounded-[6px]">
              {/* Section Header */}
              <div className="p-[1rem] border-b border-[#1F1F1F]">
                <Text_17_600_FFFFFF>
                  Available Tools ({subTools.length})
                </Text_17_600_FFFFFF>
              </div>

              {subTools.length > 0 ? (
                <>
                  {/* Select All */}
                  <div className="flex items-center gap-[0.75rem] px-[1rem] py-[0.75rem] border-b border-[#1F1F1F]">
                    <Checkbox
                      checked={isAllSelected}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                    />
                    <Text_14_400_EEEEEE>Select All</Text_14_400_EEEEEE>
                  </div>

                  {/* Sub Tools List */}
                  <div className="max-h-[300px] overflow-y-auto">
                    {subTools.map((subTool) => (
                      <div
                        key={subTool.id}
                        className="flex items-start gap-[0.75rem] px-[1rem] py-[1rem] border-b border-[#1F1F1F] last:border-b-0 cursor-pointer hover:bg-[#1F1F1F]/30"
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
                          <Text_14_400_EEEEEE className="mb-[0.25rem]">
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
                <div className="p-[1rem] text-center">
                  <Text_12_400_B3B3B3>
                    No sub-tools available for this tool.
                  </Text_12_400_B3B3B3>
                </div>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
