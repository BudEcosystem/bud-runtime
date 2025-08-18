"use client";
import React, { useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button, Card, Row, Col, Flex, Spin, Empty } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_15_600_EEEEEE,
  Text_16_400_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_500_EEEEEE,
} from "@/components/ui/text";
import dayjs from "dayjs";
import { useModels } from "@/hooks/useModels";

// Remove old interface and mock data - we'll use the Model type from useModels hook

export default function ModelsPage() {
  const { models, loading, getModelsCatalog, totalModels, totalPages } =
    useModels();
  const [currentPage, setCurrentPage] = useState(1);
  const [searchValue, setSearchValue] = useState("");
  const pageSize = 12;

  useEffect(() => {
    // Load models on mount and when page changes
    getModelsCatalog({
      page: currentPage,
      limit: pageSize,
      name: searchValue,
    });
  }, [currentPage]);

  useEffect(() => {
    // Debounce search
    const timer = setTimeout(() => {
      setCurrentPage(1);
      getModelsCatalog({
        page: 1,
        limit: pageSize,
        name: searchValue,
      });
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue]);

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
    // Return appropriate icon based on model name or provider
    if (model.name?.toLowerCase().includes("gpt")) return "simple-icons:openai";
    if (model.name?.toLowerCase().includes("claude"))
      return "simple-icons:anthropic";
    if (model.name?.toLowerCase().includes("llama")) return "simple-icons:meta";
    if (model.name?.toLowerCase().includes("dall")) return "ph:image";
    if (model.name?.toLowerCase().includes("whisper")) return "ph:microphone";
    if (model.name?.toLowerCase().includes("stable")) return "ph:palette";
    return "ph:cube";
  };

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <Text_24_500_EEEEEE>Models</Text_24_500_EEEEEE>
          </div>
          <Flex gap={16} align="center">
            <div className="relative">
              <input
                type="text"
                placeholder="Search models..."
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                className="bg-bud-bg-secondary border border-bud-border rounded-lg px-3 py-1.5 pr-8 text-sm text-bud-text-primary placeholder-bud-text-disabled focus:outline-none focus:border-bud-purple w-64"
              />
              <Icon
                icon="ph:magnifying-glass"
                className="absolute right-2 top-1/2 transform -translate-y-1/2 text-bud-text-disabled text-[1.25rem]"
              />
            </div>
            <Button
              type="text"
              icon={<Icon icon="ph:chart-line-up" />}
              className="text-bud-text-primary hover:text-bud-purple"
            >
              Benchmark history
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover px-[1.5rem]"
            >
              Model
            </Button>
          </Flex>
        </div>

        {/* Models Grid */}
        <div
          onScroll={handleScroll}
          className="overflow-y-auto"
          style={{ maxHeight: "calc(100vh - 200px)" }}
        >
          {loading && models.length === 0 ? (
            <div className="flex justify-center items-center h-64">
              <Spin size="large" />
            </div>
          ) : models.length === 0 ? (
            <Empty description="No models found" className="mt-16" />
          ) : (
            <Row gutter={[24, 24]}>
              {models.map((model) => (
                <Col key={model.id} xs={24} sm={12} lg={8}>
                  <Card
                    className="h-full bg-bud-bg-secondary border-bud-border hover:border-bud-purple hover:shadow-lg transition-all duration-300 cursor-pointer overflow-hidden"
                    styles={{ body: { padding: 0 } }}
                  >
                    <div className="p-6">
                      {/* Header with Icon and Date */}
                      <div className="flex items-start justify-between mb-6">
                        <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-bud-purple to-bud-purple-active flex items-center justify-center">
                          <Icon
                            icon={getModelIcon(model)}
                            className="text-white text-[1.5rem]"
                          />
                        </div>
                        <Text_12_400_757575>
                          {dayjs(model.modified_at || model.created_at).format(
                            "DD MMM, YYYY",
                          )}
                        </Text_12_400_757575>
                      </div>

                      {/* Model Title */}
                      <Text_19_600_EEEEEE className="mb-3 line-clamp-1">
                        {model.name}
                      </Text_19_600_EEEEEE>

                      {/* Description */}
                      <Text_13_400_EEEEEE className="mb-6 line-clamp-2 text-bud-text-muted leading-relaxed">
                        {model.description}
                      </Text_13_400_EEEEEE>

                      {/* Tags Row */}
                      <div className="flex flex-wrap gap-2 mb-6">
                        {model.endpoints_count !== undefined && (
                          <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-bud-purple/[0.125] text-bud-purple">
                            <Icon icon="ph:plug" className="text-xs" />
                            <Text_12_400_B3B3B3 className="text-bud-purple">
                              {model.endpoints_count}
                            </Text_12_400_B3B3B3>
                          </div>
                        )}

                        <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-bud-bg-tertiary text-bud-text-muted">
                          <Icon icon="ph:hard-drives" className="text-xs" />
                          <Text_12_400_B3B3B3>
                            {model.provider_type === "cloud_model"
                              ? "Cloud"
                              : "Local"}
                          </Text_12_400_B3B3B3>
                        </div>

                        {model.model_size && (
                          <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-bud-bg-tertiary text-bud-text-muted">
                            <Icon icon="ph:database" className="text-xs" />
                            <Text_12_400_B3B3B3>
                              {model.model_size}B
                            </Text_12_400_B3B3B3>
                          </div>
                        )}
                      </div>

                      {/* Author Tag */}
                      <div className="flex items-center gap-2 mb-6">
                        <Icon
                          icon="ph:user"
                          className="text-bud-text-muted text-sm"
                        />
                        <Text_12_400_B3B3B3 className="text-bud-yellow">
                          {model.author || "Unknown"}
                        </Text_12_400_B3B3B3>
                        {model.tasks && model.tasks.length > 0 && (
                          <Text_12_400_B3B3B3 className="text-bud-text-disabled">
                            {model.tasks[0].name}
                            {model.tasks.length > 1 &&
                              ` +${model.tasks.length - 1} more`}
                          </Text_12_400_B3B3B3>
                        )}
                      </div>
                    </div>

                    {/* Recommended Cluster Section */}
                    <div className="bg-bud-bg-tertiary px-6 py-4 border-t border-bud-border rounded-b-lg">
                      <Text_12_400_757575 className="mb-2">
                        Recommended Cluster
                      </Text_12_400_757575>
                      {model.model_cluster_recommended ? (
                        <div>
                          <Text_13_400_EEEEEE className="mb-2">
                            {model.model_cluster_recommended.cluster?.name}
                          </Text_13_400_EEEEEE>
                          <div className="flex flex-wrap gap-1">
                            {model.model_cluster_recommended.cluster
                              ?.availability_percentage && (
                              <span className="text-xs px-2 py-0.5 rounded bg-bud-bg-secondary text-bud-text-muted">
                                {
                                  model.model_cluster_recommended.cluster
                                    .availability_percentage
                                }
                                % Available
                              </span>
                            )}
                            {model.model_cluster_recommended
                              .cost_per_million_tokens && (
                              <span className="text-xs px-2 py-0.5 rounded bg-bud-bg-secondary text-bud-text-muted">
                                $
                                {Number(
                                  model.model_cluster_recommended
                                    .cost_per_million_tokens,
                                ).toFixed(2)}{" "}
                                / 1M
                              </span>
                            )}
                          </div>
                        </div>
                      ) : (
                        <Text_13_400_EEEEEE className="text-bud-text-disabled">
                          No data available
                        </Text_13_400_EEEEEE>
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
    </DashboardLayout>
  );
}
