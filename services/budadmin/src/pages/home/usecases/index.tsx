"use client";
import { Box, Flex } from "@radix-ui/themes";
import { useEffect, useState } from "react";
import React from "react";
import DashBoardLayout from "../layout";
import {
  Text_11_400_808080,
  Text_12_400_6A6E76,
  Text_13_400_B3B3B3,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import PageHeader from "@/components/ui/pageHeader";
import { useLoader } from "src/context/appContext";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { PlusOutlined, MoreOutlined } from "@ant-design/icons";
import { Tag, Tooltip, Dropdown, ConfigProvider } from "antd";
import { formatDistanceToNow } from "date-fns";
import { useDrawer } from "src/hooks/useDrawer";
import { useUseCases } from "src/stores/useUseCases";
import { Template, ComponentType } from "@/lib/budusecases";

// Component type badge colors
const componentTypeColors: Record<ComponentType, string> = {
  model: "#8B5CF6",
  llm: "#8B5CF6",
  embedder: "#F59E0B",
  reranker: "#EF4444",
  vector_db: "#10B981",
  memory_store: "#3B82F6",
  helm: "#06B6D4",
};

// Category display labels
const categoryLabels: Record<string, string> = {
  rag: "RAG",
  chatbot: "Chatbot",
  agent: "Agent",
};

const TemplateCard = ({
  template,
  onClick,
  onDeploy,
}: {
  template: Template;
  onClick: () => void;
  onDeploy: () => void;
}) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className="flex flex-col justify-between w-full bg-[#101010] border border-[#1F1F1F] rounded-lg pt-[1.54em] min-h-[325px] cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] hover:border-[#965CDE] transition-all duration-200 overflow-hidden focus:outline-none focus:ring-2 focus:ring-[#965CDE] focus:ring-offset-2 focus:ring-offset-[#000000]"
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`View template: ${template.display_name}. ${template.components?.length || 0} components.`}
    >
      <div className="px-[1.6rem] pb-[1.54em]">
        {/* Header with icon and actions */}
        <div className="pr-0 flex justify-between items-start gap-3">
          <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center text-xl">
            🚀
          </div>
          <ConfigProvider
            theme={{
              token: {
                colorBgElevated: "#111113",
                colorText: "#EEEEEE",
                controlItemBgHover: "#1F1F1F",
                boxShadowSecondary: "0 0 0 1px #1F1F1F",
              },
            }}
          >
            <Dropdown
              menu={{
                items: [
                  {
                    key: "deploy",
                    label: "Deploy",
                    onClick: (e) => {
                      e.domEvent.stopPropagation();
                      onDeploy();
                    },
                  },
                ],
              }}
              trigger={["hover"]}
              placement="bottomRight"
            >
              <div
                className="w-[1.5rem] h-[1.5rem] flex items-center justify-center rounded hover:bg-[#1F1F1F] transition-colors cursor-pointer"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreOutlined className="text-[#B3B3B3] text-[1.2rem]" rotate={180} />
              </div>
            </Dropdown>
          </ConfigProvider>
        </div>

        {/* Date */}
        <div className="mt-[1.3rem]">
          <Text_11_400_808080>
            {template.created_at
              ? formatDistanceToNow(new Date(template.created_at), { addSuffix: true })
              : "Recently created"}
          </Text_11_400_808080>
        </div>

        {/* Name */}
        <div className="mt-[.75rem]">
          <Text_17_600_FFFFFF className="max-w-[100] truncate w-[calc(100%-20px)] leading-[0.964375rem]">
            {template.display_name}
          </Text_17_600_FFFFFF>
        </div>

        {/* Description */}
        <Text_13_400_B3B3B3 className="mt-2 line-clamp-2 text-[12px]">
          {template.description || "No description provided"}
        </Text_13_400_B3B3B3>

        {/* Tags */}
        <Flex gap="2" wrap="wrap" className="mt-4" align="center">
          {template.category && (
            <Tag
              className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
              style={{ backgroundColor: "#8F55D62B", color: "#965CDE" }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]">
                {categoryLabels[template.category] || template.category}
              </div>
            </Tag>
          )}
          {template.components?.length > 0 && (
            <Tag
              className="text-[#B3B3B3] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
              style={{ backgroundColor: "#1F1F1F" }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]">
                {template.components.length} Component{template.components.length !== 1 ? "s" : ""}
              </div>
            </Tag>
          )}
          <Tag
            className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
            style={{ backgroundColor: "#1F1F1F", color: "#6A6E76" }}
          >
            <div className="text-[0.625rem] font-[400] leading-[100%]">
              v{template.version}
            </div>
          </Tag>
          {/* Access mode indicators */}
          {template.access?.ui?.enabled && (
            <Tooltip title="Supports web UI access">
              <Tag
                className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                style={{ backgroundColor: "#3B82F620", color: "#3B82F6" }}
              >
                <div className="text-[0.625rem] font-[400] leading-[100%]">
                  UI
                </div>
              </Tag>
            </Tooltip>
          )}
          {template.access?.api?.enabled && (
            <Tooltip title="Supports API access">
              <Tag
                className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                style={{ backgroundColor: "#10B98120", color: "#10B981" }}
              >
                <div className="text-[0.625rem] font-[400] leading-[100%]">
                  API
                </div>
              </Tag>
            </Tooltip>
          )}
        </Flex>
      </div>

      {/* Footer - component type badges */}
      <div className="px-[1.6rem] bg-[#161616] pt-[1.4rem] pb-[1.5rem] border-t-[.5px] border-t-[#1F1F1F]">
        <Text_12_400_6A6E76 className="mb-[.7rem]">Components</Text_12_400_6A6E76>
        <Flex gap="2" wrap="wrap" align="center">
          {template.components?.map((comp) => {
            const color = componentTypeColors[comp.component_type] || "#6A6E76";
            return (
              <Tooltip key={comp.id || comp.name} title={comp.display_name || comp.name}>
                <Tag
                  className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                  style={{ backgroundColor: `${color}20`, color }}
                >
                  <div className="text-[0.625rem] font-[400] leading-[100%]">
                    {comp.component_type}
                  </div>
                </Tag>
              </Tooltip>
            );
          })}
          {(!template.components || template.components.length === 0) && (
            <Tag
              className="text-[#6A6E76] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
              style={{ backgroundColor: "#1F1F1F" }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]">
                No components
              </div>
            </Tag>
          )}
        </Flex>
      </div>
    </div>
  );
};

const UseCases = () => {
  const [isMounted, setIsMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const { showLoader, hideLoader } = useLoader();
  const {
    templates,
    templatesLoading,
    fetchTemplates,
    selectTemplate,
  } = useUseCases();
  const { openDrawerWithStep, openDrawer } = useDrawer();

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

  const handleTemplateClick = (template: Template) => {
    selectTemplate(template);
    openDrawer("view-usecase-template", { template });
  };

  const handleDeployTemplate = (template: Template) => {
    selectTemplate(template);
    openDrawer("view-usecase-template", { template, autoDeploy: true });
  };

  useEffect(() => {
    if (isMounted) {
      showLoader();
      fetchTemplates().finally(() => hideLoader());
    }
  }, [isMounted]);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <DashBoardLayout>
      <Box className="boardPageView">
        <Box className="boardPageTop">
          <PageHeader
            headding="Use Cases"
            ButtonIcon={PlusOutlined}
            buttonLabel="Template"
            buttonPermission={true}
            buttonAction={() => {
              openDrawerWithStep("create-usecase-template");
            }}
            rightComponent={
              <SearchHeaderInput
                placeholder="Search templates..."
                searchValue={searchTerm}
                setSearchValue={setSearchTerm}
                classNames="mr-[.6rem]"
              />
            }
          />
        </Box>

        <Box className="boardMainContainer listingContainer" id="usecases-list">
          {!filteredTemplates?.length && !searchTerm && !templatesLoading && (
            <NoDataFount
              classNames="h-[50vh]"
              textMessage="No use case templates available. Create your first template to get started."
            />
          )}
          {searchTerm && !filteredTemplates?.length && (
            <NoDataFount
              classNames="h-[50vh]"
              textMessage={`No templates found for "${searchTerm}"`}
            />
          )}
          <div className="grid gap-[1.1rem] grid-cols-1 md:grid-cols-2 lg:grid-cols-3 mt-[2.95rem] pb-6">
            {filteredTemplates?.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                onClick={() => handleTemplateClick(template)}
                onDeploy={() => handleDeployTemplate(template)}
              />
            ))}
          </div>
        </Box>
      </Box>
    </DashBoardLayout>
  );
};

export default UseCases;
