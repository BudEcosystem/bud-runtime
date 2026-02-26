/**
 * SelectTemplate - Step 1 of the Deploy Use Case wizard
 *
 * Displays a searchable list of templates with checkbox selection.
 * User selects one template and clicks Next to proceed to configuration.
 * Follows the same pattern as DeployModelTemplateSelect.
 */

import React, { useEffect, useState } from "react";
import { Checkbox, Tag, Tooltip } from "antd";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_B3B3B3,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { useUseCases } from "src/stores/useUseCases";
import { useDrawer } from "src/hooks/useDrawer";
import type { Template, ComponentType } from "@/lib/budusecases";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";

const componentTypeColors: Record<ComponentType | string, string> = {
  model: "#8B5CF6",
  llm: "#8B5CF6",
  embedder: "#F59E0B",
  reranker: "#EF4444",
  memory_store: "#3B82F6",
  helm: "#06B6D4",
};

const categoryLabels: Record<string, string> = {
  rag: "RAG",
  chatbot: "Chatbot",
  agent: "Agent",
};

function TemplateRow({
  template,
  selected,
  onClick,
}: {
  template: Template;
  selected: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      className="py-[1.1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box"
    >
      <div className="mr-[.7rem]">
        <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[5px] flex justify-center items-center shrink-0 grow-0 text-[0.8rem]">
          🚀
        </div>
      </div>
      <div className="flex justify-between w-full flex-col">
        <div className="flex items-center justify-between h-4">
          <div className="flex items-center gap-2">
            <Text_14_400_EEEEEE className="leading-[150%]">
              {template.display_name}
            </Text_14_400_EEEEEE>
            {template.category && (
              <Tag
                className="border-[0] rounded-[6px] flex justify-center items-center py-[.1rem] px-[.3rem]"
                style={{ backgroundColor: "#8F55D62B", color: "#965CDE", margin: 0 }}
              >
                <div className="text-[0.525rem] font-[400] leading-[100%]">
                  {categoryLabels[template.category] || template.category}
                </div>
              </Tag>
            )}
          </div>
          <div
            style={{
              display: hover || selected ? "flex" : "none",
            }}
          >
            <Checkbox
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] mt-[.85rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="overflow-hidden line-clamp-2 leading-[170%]">
          {template.description || "-"}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

export default function SelectTemplate() {
  const {
    templates,
    templatesLoading,
    fetchTemplates,
    selectTemplate,
    selectedTemplate,
  } = useUseCases();
  const { openDrawerWithStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    fetchTemplates();
  }, []);

  const filteredTemplates = React.useMemo(() => {
    const valid = templates?.filter((t): t is Template => t != null && t.id != null) || [];
    if (!searchTerm) return valid;
    const term = searchTerm.toLowerCase();
    return valid.filter(
      (t) =>
        t.display_name?.toLowerCase().includes(term) ||
        t.name?.toLowerCase().includes(term) ||
        t.description?.toLowerCase().includes(term) ||
        t.category?.toLowerCase().includes(term) ||
        t.tags?.some((tag) => tag.toLowerCase().includes(term))
    );
  }, [templates, searchTerm]);

  return (
    <BudForm
      data={{}}
      disableNext={!selectedTemplate?.id}
      onNext={() => openDrawerWithStep("deploy-usecase-name")}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Template"
            description="Choose a use case template to deploy."
          />
          <div className="px-[1.4rem] pt-[1rem] rounded-es-lg rounded-ee-lg pb-[.4rem]">
            <div className="flex items-center justify-between gap-[.7rem]">
              <SearchHeaderInput
                placeholder="Search Templates"
                searchValue={searchTerm}
                setSearchValue={setSearchTerm}
                expanded
              />
            </div>
          </div>

          {templatesLoading && (
            <div className="py-8 text-center">
              <Text_10_400_B3B3B3>Loading templates...</Text_10_400_B3B3B3>
            </div>
          )}

          {!templatesLoading && filteredTemplates.length === 0 && (
            <div className="py-8 text-center">
              <Text_10_400_B3B3B3>
                {searchTerm
                  ? `No templates found for "${searchTerm}"`
                  : "No templates available."}
              </Text_10_400_B3B3B3>
            </div>
          )}

          <div className="pt-[.6rem]">
            {filteredTemplates.map((template) => (
              <TemplateRow
                key={template.id}
                template={template}
                selected={selectedTemplate?.id === template.id}
                onClick={() => selectTemplate(template)}
              />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
