"use client";
import React, { useEffect, useState, useCallback } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Button,
  Card,
  Row,
  Col,
  Flex,
  Spin,
  Empty,
  Popover,
  Select,
  Slider,
  ConfigProvider,
  Tag,
} from "antd";
import { FilterOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import { useDrawer } from "@/hooks/useDrawer";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";
const assetBaseUrl = process.env.NEXT_PUBLIC_BASE_URL;
import {
  Text_13_400_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_500_EEEEEE,
} from "@/components/ui/text";
import dayjs from "dayjs";
import { useModels, cloudProviders } from "@/hooks/useModels";
import { PrimaryButton, SecondaryButton } from "@/components/ui/button";
import ModelTags from "@/components/ui/ModelTags";

// Filter interface
interface Filters {
  name?: string;
  endpoint_name?: string;
  author?: string;
  tasks?: string[];
  model_size_min?: number;
  model_size_max?: number;
  modality?: string[];
  table_source?: string[];
}

const defaultFilter: Filters = {
  name: "",
  endpoint_name: "",
  modality: [],
  model_size_min: undefined,
  model_size_max: undefined,
  table_source: ["model"],
};

// Selected filters display component
const SelectedFilters = ({
  filters,
  removeTag,
}: {
  filters: Filters;
  removeTag: (key: string, item: any) => void;
}) => {
  return (
    <div className="flex justify-start gap-2 items-center flex-wrap mb-4">
      {/* Author and Tasks filters removed as APIs are not available */}
      {filters?.model_size_min !== undefined && (
        <Tag
          closable
          onClose={() => removeTag("model_size_min", filters.model_size_min)}
          className="bg-bud-yellow/20 text-bud-yellow border-bud-yellow/40"
        >
          Min size: {filters.model_size_min}B
        </Tag>
      )}
      {filters?.model_size_max !== undefined && (
        <Tag
          closable
          onClose={() => removeTag("model_size_max", filters.model_size_max)}
          className="bg-bud-yellow/20 text-bud-yellow border-bud-yellow/40"
        >
          Max size: {filters.model_size_max}B
        </Tag>
      )}
      {filters?.modality?.map((item, index) => (
        <Tag
          key={index}
          closable
          onClose={() => removeTag("modality", item)}
          className="bg-bud-yellow/20 text-bud-yellow border-bud-yellow/40"
        >
          {cloudProviders.find((cp) => cp.modality === item)?.label || item}
        </Tag>
      ))}
    </div>
  );
};

export default function ModelsPage() {
  const {
    models,
    loading,
    getModelsCatalog,
    totalModels,
    totalPages,
    setSelectedModel,
  } = useModels();
  const { openDrawer } = useDrawer();

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(12);
  const [tempFilter, setTempFilter] = useState<Filters>(defaultFilter);
  const [filter, setFilter] = useState<Filters>(defaultFilter);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filterReset, setFilterReset] = useState(false);

  // Load models with filters
  const load = useCallback(
    async (filterParams: Filters) => {
      await getModelsCatalog({
        page: currentPage,
        limit: pageSize,
        name: filterParams.endpoint_name,
        modality: filterParams.modality?.length
          ? filterParams.modality
          : undefined,
        model_size_min: filterParams.model_size_min,
        model_size_max: filterParams.model_size_max,
        table_source: "model",
      });
    },
    [currentPage, pageSize, getModelsCatalog],
  );

  // Initialize tasks and authors - removed API calls
  // useEffect(() => {
  //   getTasks();
  //   getAuthors();
  // }, []);

  // Load models on filter or page change
  useEffect(() => {
    const timer = setTimeout(() => {
      load(filter);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter, currentPage]);

  // Handle filter popup
  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
    if (open) {
      setTempFilter(filter);
    }
  };

  // Apply filters
  const applyFilter = () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    setFilterReset(false);
  };

  // Reset filters
  const resetFilter = () => {
    setTempFilter(defaultFilter);
    setFilterReset(true);
  };

  // Remove individual filter tag
  const removeSelectedTag = (key: string, item: any) => {
    const newFilter = { ...filter };

    if (key === "model_size_max" || key === "model_size_min") {
      delete newFilter.model_size_max;
      delete newFilter.model_size_min;
    } else if (key === "modality") {
      newFilter[key] = newFilter[key]?.filter((element) => element !== item);
    }

    setFilter(newFilter);
    setTempFilter(newFilter);
    setCurrentPage(1);
  };

  // Auto apply after reset
  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  // Handle infinite scroll
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const element = e.currentTarget;
    const bottom =
      element.scrollHeight - element.scrollTop === element.clientHeight;
    if (
      bottom &&
      models.length < totalModels &&
      currentPage < totalPages &&
      !loading
    ) {
      setCurrentPage(currentPage + 1);
    }
  };

  const getModelIcon = (model: any) => {
    // Return an object that indicates whether it's a URL or an icon name
    if (model.icon) {
      // If icon exists, it's a URL
      const iconUrl = model.icon.startsWith("http")
        ? model.icon
        : `${assetBaseUrl}/${model.icon.startsWith("/") ? model.icon.slice(1) : model.icon}`;
      return { type: "url", value: iconUrl };
    }

    // Fallback to iconify icons
    const name = model.name?.toLowerCase() || "";
    if (name.includes("gpt"))
      return { type: "icon", value: "simple-icons:openai" };
    if (name.includes("claude"))
      return { type: "icon", value: "simple-icons:anthropic" };
    if (name.includes("llama"))
      return { type: "icon", value: "simple-icons:meta" };
    if (name.includes("dall")) return { type: "icon", value: "ph:image" };
    if (name.includes("whisper"))
      return { type: "icon", value: "ph:microphone" };
    if (name.includes("stable")) return { type: "icon", value: "ph:palette" };
    return { type: "icon", value: "ph:cube" };
  };

  const handleModelClick = (model: any) => {
    setSelectedModel(model);
    openDrawer("view-model", {});
  };

  return (
    <DashboardLayout>
      <div className="h-full flex flex-col p-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-6 flex-shrink-0 pt-[1.5rem] pb-[1rem]">
          <div>
            <Text_24_500_EEEEEE>Models</Text_24_500_EEEEEE>
          </div>
          <Flex gap={16} align="center">
            {/* Search Input */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search by name"
                value={filter.name}
                onChange={(e) => {
                  setFilter({ ...filter, name: e.target.value });
                  setCurrentPage(1);
                }}
                className="bg-bud-bg-secondary border border-bud-border rounded-lg px-3 py-1.5 pr-8 text-sm text-bud-text-primary placeholder-bud-text-disabled focus:outline-none focus:border-bud-purple w-64"
              />
              <Icon
                icon="ph:magnifying-glass"
                className="absolute right-2 top-1/2 transform -translate-y-1/2 text-bud-text-disabled text-[1.25rem]"
              />
            </div>

            {/* Filter Button */}
            <div className="hidden">
              <ConfigProvider
                theme={{
                  token: {
                    colorBgElevated: "#111113",
                    colorBorder: "#1F1F1F",
                  },
                }}
              >
                <Popover
                  open={filterOpen}
                  onOpenChange={handleOpenChange}
                  placement="bottomRight"
                  trigger={["click"]}
                  content={
                    <div className="bg-[#111113] w-[350px]">
                      <div className="p-6">
                        <div className="text-white text-sm font-medium mb-1">
                          Filter
                        </div>
                        <div className="text-xs text-bud-text-disabled mb-4">
                          Apply the following filters to find model of your
                          choice.
                        </div>

                        <div className="space-y-4">
                          {/* Author Select - Commented out as API is not available */}
                          {/* <div>
                          <label className="text-xs text-bud-text-muted mb-1 block">Author</label>
                          <Select
                            placeholder="Select Author"
                            className="w-full"
                            value={tempFilter.author}
                            onChange={(value) => setTempFilter({ ...tempFilter, author: value })}
                            allowClear
                            options={authors?.map((author) => ({
                              label: author,
                              value: author,
                            }))}
                          />
                        </div> */}

                          {/* Task Select - Commented out as API is not available */}
                          {/* <div>
                          <label className="text-xs text-bud-text-muted mb-1 block">Task</label>
                          <Select
                            placeholder="Select Task"
                            className="w-full"
                            mode="multiple"
                            value={tempFilter.tasks}
                            onChange={(value) => setTempFilter({ ...tempFilter, tasks: value })}
                            options={tasks?.map((task) => ({
                              label: task.name,
                              value: task.name,
                            }))}
                          />
                        </div> */}

                          {/* Model Size Slider */}
                          <div>
                            <label className="text-xs text-bud-text-muted mb-2 block">
                              Model Size (B)
                            </label>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-bud-text-disabled">
                                1
                              </span>
                              <Slider
                                className="flex-1"
                                min={1}
                                max={500}
                                range
                                value={[
                                  tempFilter.model_size_min || 1,
                                  tempFilter.model_size_max || 500,
                                ]}
                                onChange={(value) => {
                                  setTempFilter({
                                    ...tempFilter,
                                    model_size_min: value[0],
                                    model_size_max: value[1],
                                  });
                                }}
                                tooltip={{ open: true }}
                              />
                              <span className="text-xs text-bud-text-disabled">
                                500
                              </span>
                            </div>
                          </div>

                          {/* Modality Select */}
                          <div>
                            <label className="text-xs text-bud-text-muted mb-1 block">
                              Modality
                            </label>
                            <Select
                              placeholder="Select Modality"
                              className="w-full"
                              mode="multiple"
                              value={tempFilter.modality}
                              onChange={(value) =>
                                setTempFilter({
                                  ...tempFilter,
                                  modality: value,
                                })
                              }
                              options={cloudProviders.map((modality) => ({
                                label: modality.label,
                                value: modality.modality,
                              }))}
                            />
                          </div>

                          {/* Action Buttons */}
                          <div className="flex justify-between pt-2">
                            <SecondaryButton onClick={resetFilter}>
                              Reset
                            </SecondaryButton>
                            <PrimaryButton onClick={applyFilter}>
                              Apply
                            </PrimaryButton>
                          </div>
                        </div>
                      </div>
                    </div>
                  }
                >
                  <Button
                    icon={<FilterOutlined />}
                    className="!bg-[var(--bg-primary)] text-bud-text-primary hover:text-bud-purple border-bud-border"
                  >
                    Filter
                  </Button>
                </Popover>
              </ConfigProvider>
            </div>
          </Flex>
        </div>

        {/* Selected Filters */}
        {(filter.modality?.length ||
          filter.model_size_min !== undefined ||
          filter.model_size_max !== undefined) && (
          <div className="flex-shrink-0">
            <SelectedFilters filters={filter} removeTag={removeSelectedTag} />
          </div>
        )}

        {/* Models Grid */}
        <div
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 relative"
        >
          {loading && models.length === 0 ? (
            <div className="flex justify-center items-center h-64">
              <Spin size="large" />
            </div>
          ) : models.length === 0 ? (
            <Empty
              description={
                filter.name ||
                filter.modality?.length ||
                filter.model_size_min !== undefined ||
                filter.model_size_max !== undefined
                  ? `No models found`
                  : "No models available"
              }
              className="mt-16"
            />
          ) : (
            <Row gutter={[24, 24]} className="w-full">
              {models.map((model) => (
                <Col key={model.id} xs={24} sm={12} lg={8} xl={8} xxl={6}>
                  <Card
                    className="h-full bg-bud-bg-secondary border-bud-border hover:border-bud-purple hover:shadow-lg transition-all duration-300 cursor-pointer flex flex-col overflow-hidden rounded-lg"
                    styles={{
                      body: {
                        padding: 0,
                        display: "flex",
                        flexDirection: "column",
                        height: "100%",
                      },
                    }}
                    onClick={() => handleModelClick(model)}
                  >
                    <div className="p-6 flex-1 flex flex-col relative">
                      <div className="flex-1">
                        {/* Header with Icon and Date */}
                        <div className="flex items-start justify-between mb-4">
                          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-bud-purple/20 to-bud-purple/10 flex items-center justify-center">
                            {(() => {
                              const iconData = getModelIcon(model);
                              return iconData.type === "url" ? (
                                <img
                                  src={iconData.value}
                                  alt={model.name}
                                  className="w-6 h-6 object-contain"
                                  onError={(e) => {
                                    // Fallback to default icon on error
                                    e.currentTarget.style.display = "none";
                                  }}
                                />
                              ) : (
                                <Icon
                                  icon={iconData.value}
                                  className="text-bud-purple text-[1.5rem]"
                                />
                              );
                            })()}
                          </div>
                          <div className="text-xs font-normal text-gray-600 dark:text-gray-400">
                            {dayjs(
                              model.modified_at || model.created_at,
                            ).format("DD MMM, YYYY")}
                          </div>
                        </div>

                        {/* Model Title */}
                        <Text_19_600_EEEEEE className="mb-3 line-clamp-1 !leading-[130%]">
                          {model.endpoint_name}
                        </Text_19_600_EEEEEE>

                        {/* Description */}
                        <div className="mb-4 min-h-[2.5rem]">
                          <p className="text-sm text-bud-text-muted leading-relaxed line-clamp-2">
                            {model.description || "No description available"}
                          </p>
                        </div>

                        {/* Model Tags */}
                        <ModelTags 
                          model={{
                            ...model,
                            endpoints_count: model.supported_endpoints 
                              ? Object.values(model.supported_endpoints).filter((e: any) => e.enabled).length 
                              : model.endpoints_count
                          }} 
                          maxTags={3} 
                          limit={true} 
                        />

                        {/* Author and Tasks */}
                        <div className="flex items-center gap-2 flex-wrap">
                          {model.author && (
                            <div className="flex items-center gap-1">
                              <Icon
                                icon="ph:user"
                                className="text-bud-text-muted text-xs"
                              />
                              <span className="text-xs text-[--color-yellow]">
                                {model.author}
                              </span>
                            </div>
                          )}
                          {model.tasks?.length > 0 && (
                            <span className="text-xs text-bud-text-disabled">
                              {model.tasks[0].name}
                              {model.tasks.length > 1 &&
                                ` +${model.tasks.length - 1} more`}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Pricing Section - Always at bottom */}
                    <div className="bg-bud-bg-tertiary px-6 py-4 border-t border-bud-border flex-shrink-0 rounded-b-lg">
                      <div className="text-xs font-normal text-gray-700 dark:text-gray-400 mb-2">
                        Pricing Details
                      </div>
                      {model.pricing ? (
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:arrow-down"
                              className="text-bud-text-muted text-xs"
                            />
                            <Text_13_400_EEEEEE>
                              Input:{" "}
                              {model.pricing.input_cost === 0
                                ? "Free"
                                : `${model.pricing.input_cost} ${model.pricing.currency} / ${model.pricing.per_tokens} Tokens`}
                            </Text_13_400_EEEEEE>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:arrow-up"
                              className="text-bud-text-muted text-xs"
                            />
                            <Text_13_400_EEEEEE>
                              Output:{" "}
                              {model.pricing.output_cost === 0
                                ? "Free"
                                : `${model.pricing.output_cost} ${model.pricing.currency} / ${model.pricing.per_tokens} Tokens`}
                            </Text_13_400_EEEEEE>
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs px-2 py-1 rounded bg-bud-bg-secondary text-bud-text-disabled">
                          Pricing not available
                        </span>
                      )}
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
          {loading && models.length > 0 && (
            <div className="flex justify-center items-center py-4">
              <Spin />
            </div>
          )}
        </div>
      </div>

      {/* Model Detail Drawer */}
      <BudDrawer />
    </DashboardLayout>
  );
}
