"use client";
import { useState, useEffect, useCallback } from "react";
import React from "react";
import { Image, Spin } from "antd";
import {
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
} from "../../../../components/ui/text";
import RadarChart from "@/components/charts/radarChart";
import HeatmapChart from "@/components/charts/heatmapChart";
import { useComparisonStore } from "@/stores/useComparisonStore";
import { assetBaseUrl } from "@/components/environment";

// Gradient styles for sidebar container
const SIDEBAR_BORDER_GRADIENT = "linear-gradient(180deg, #1F1F1F 0%, #030303 100%)";
const SIDEBAR_BACKGROUND_GRADIENT = "linear-gradient(180deg, rgba(0, 0, 0, 0.5) 0%, #0A0A0A 75.77%, #0A0A0A 85%, #121212 100%)";

const EvaluationSummary = () => {
  const [searchValue, setSearchValue] = useState("");

  // Get data and actions from the comparison store
  const {
    selectedDeploymentIds,
    selectedTraitIds,
    isLoadingRadar,
    isLoadingHeatmap,
    isInitialized,
    initializeData,
    toggleDeploymentSelection,
    toggleTraitSelection,
    refreshCharts,
    getDeployments,
    getTraits,
    getRadarChartData,
    getHeatmapChartData,
  } = useComparisonStore();

  // Get deployments and traits derived from radar data
  const deployments = getDeployments();
  const traits = getTraits();

  // Initialize data on mount
  useEffect(() => {
    if (!isInitialized) {
      initializeData();
    }
  }, [isInitialized, initializeData]);

  // Refresh charts when selections change
  useEffect(() => {
    if (isInitialized) {
      refreshCharts();
    }
  }, [selectedDeploymentIds, selectedTraitIds, isInitialized, refreshCharts]);

  // Get transformed chart data
  const radarChartData = getRadarChartData();
  const heatmapChartData = getHeatmapChartData();

  // Filter deployments based on search
  const filteredDeployments = deployments.filter((deployment) =>
    deployment.endpoint_name.toLowerCase().includes(searchValue.toLowerCase()) ||
    deployment.model_display_name?.toLowerCase().includes(searchValue.toLowerCase()) ||
    deployment.model_name.toLowerCase().includes(searchValue.toLowerCase())
  );

  // Filter traits based on search
  const filteredTraits = traits.filter((trait) =>
    trait.name.toLowerCase().includes(searchValue.toLowerCase())
  );

  const handleDeploymentToggle = useCallback(
    (deploymentId: string) => {
      toggleDeploymentSelection(deploymentId);
    },
    [toggleDeploymentSelection]
  );

  const handleTraitClick = useCallback(
    (traitId: string) => {
      toggleTraitSelection(traitId);
    },
    [toggleTraitSelection]
  );

  // Check if charts are loading
  const isChartsLoading = isLoadingRadar || isLoadingHeatmap;

  return (
    <div className="w-full h-full overflow-y-auto">
      <div className="flex flex-col gap-6 p-6">
        {/* Top Section - Sidebar and Radar Chart */}
        <div className="flex gap-6">
          {/* Left Section - Following Figma specs */}
          <div className="w-[254px] flex-shrink-0">
            {/* Outer wrapper for gradient border */}
            <div
              className="rounded-[8px] p-[1px]"
              style={{ background: SIDEBAR_BORDER_GRADIENT }}
            >
              {/* Inner container with background */}
              <div
                className="rounded-[7px] p-4 flex flex-col gap-6"
                style={{ background: SIDEBAR_BACKGROUND_GRADIENT }}
              >
                {/* Search Section */}
                <div className="bg-[rgba(255,255,255,0.03)] rounded-[12px] h-[2.125rem] flex items-center px-[10px]">
                  <div className="flex items-center gap-3 w-full">
                    <div className="w-[14px] h-[14px] opacity-50">
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle
                          cx="5.5"
                          cy="5.5"
                          r="4.5"
                          stroke="#B3B3B3"
                          strokeWidth="1.2"
                        />
                        <path
                          d="M9 9L12 12"
                          stroke="#B3B3B3"
                          strokeWidth="1.2"
                          strokeLinecap="round"
                        />
                      </svg>
                    </div>
                    <input
                      type="text"
                      value={searchValue}
                      onChange={(e) => setSearchValue(e.target.value)}
                      placeholder="Search"
                      className="bg-transparent text-[#757575] text-[12px] outline-none flex-1 placeholder:text-[#757575]"
                    />
                  </div>
                </div>

                {/* Deployments Section */}
                <div className="flex flex-col gap-3">
                  <div className="px-2">
                    <Text_14_400_B3B3B3 className="text-[14px] leading-[20px] font-normal">
                      Deployments
                    </Text_14_400_B3B3B3>
                  </div>
                  <div className="flex flex-col gap-1 max-h-[200px] overflow-y-auto">
                    {isLoadingRadar && !isInitialized ? (
                      <div className="flex justify-center py-4">
                        <Spin size="small" />
                      </div>
                    ) : filteredDeployments.length === 0 ? (
                      <div className="px-2 py-4 text-center">
                        <Text_14_400_B3B3B3 className="text-[12px]">
                          {searchValue ? "No deployments found" : "No deployments available"}
                        </Text_14_400_B3B3B3>
                      </div>
                    ) : (
                      filteredDeployments.map((deployment) => {
                        const isSelected = selectedDeploymentIds.includes(deployment.id);
                        const deploymentColor = deployment.color;

                        return (
                          <div
                            key={deployment.id}
                            className={`flex items-center gap-2 py-[8px] px-[10px] rounded-[8px] cursor-pointer transition-all ${isSelected
                                ? "bg-[rgba(255,255,255,0.03)]"
                                : "hover:bg-[rgba(255,255,255,0.02)]"
                              }`}
                            onClick={() => handleDeploymentToggle(deployment.id)}
                          >
                            <div className="w-[1.25rem] h-[1.25rem] rounded-[6px] bg-cover bg-center bg-[#1F1F1F] flex items-center justify-center overflow-hidden">
                              <Image
                                preview={false}
                                style={{ width: "auto", height: "1.25rem" }}
                                src={deployment.model_icon}
                                alt={deployment.endpoint_name}
                                fallback="/icons/huggingFace.png"
                              />
                            </div>
                            <div className="flex-1 min-w-0">
                              <Text_14_400_EEEEEE className="text-[14px] leading-[19px] truncate block">
                                {deployment.endpoint_name}
                              </Text_14_400_EEEEEE>
                            </div>
                            <div
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: deploymentColor }}
                            />
                            <div className="w-3 h-3 opacity-0 hover:opacity-100 transition-opacity flex-shrink-0">
                              <svg
                                width="12"
                                height="12"
                                viewBox="0 0 12 12"
                                fill="none"
                              >
                                <circle cx="6" cy="2" r="1" fill="#B3B3B3" />
                                <circle cx="6" cy="6" r="1" fill="#B3B3B3" />
                                <circle cx="6" cy="10" r="1" fill="#B3B3B3" />
                              </svg>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Traits Section */}
                <div className="flex flex-col gap-3">
                  <div className="px-2">
                    <Text_14_400_B3B3B3 className="text-[14px] leading-[20px] font-normal">
                      Traits
                    </Text_14_400_B3B3B3>
                  </div>
                  <div className="flex flex-col gap-1 max-h-[200px] overflow-y-auto">
                    {isLoadingRadar && !isInitialized ? (
                      <div className="flex justify-center py-4">
                        <Spin size="small" />
                      </div>
                    ) : filteredTraits.length === 0 ? (
                      <div className="px-2 py-4 text-center">
                        <Text_14_400_B3B3B3 className="text-[12px]">
                          {searchValue ? "No traits found" : "No traits available"}
                        </Text_14_400_B3B3B3>
                      </div>
                    ) : (
                      filteredTraits.map((trait) => {
                        const isSelected = selectedTraitIds.includes(trait.id);
                        return (
                          <div
                            key={trait.id}
                            className={`flex items-center gap-2 py-[8px] px-[10px] rounded-[8px] cursor-pointer transition-all ${isSelected
                                ? "bg-[rgba(255,255,255,0.03)]"
                                : "hover:bg-[rgba(255,255,255,0.02)]"
                              }`}
                            onClick={() => handleTraitClick(trait.id)}
                          >
                            <div className="w-[1.25rem] h-[1.25rem] rounded-[6px] bg-cover bg-center bg-[#1F1F1F] flex items-center justify-center overflow-hidden">
                              {trait.icon && (
                                <Image
                                  preview={false}
                                  src={`${assetBaseUrl}${trait.icon}`}
                                  style={{ width: "auto", height: "1.25rem" }}
                                  alt={trait.name}
                                  fallback="/icons/huggingFace.png"
                                />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <Text_14_400_EEEEEE className="text-[14px] leading-[19px] truncate block">
                                {trait.name}
                              </Text_14_400_EEEEEE>
                            </div>
                            {isSelected && (
                              <div className="w-4 h-4 flex-shrink-0">
                                <svg
                                  width="16"
                                  height="16"
                                  viewBox="0 0 16 16"
                                  fill="none"
                                >
                                  <path
                                    d="M13.3334 4L6.00008 11.3333L2.66675 8"
                                    stroke="#22C55E"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Radar Chart */}
          <div className="flex-1 h-[500px] bg-transparent rounded-lg p-6 relative">
            {isChartsLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-[#0A0A0A]/50 z-10 rounded-lg">
                <Spin size="large" />
              </div>
            )}
            {radarChartData.indicators.length > 0 ? (
              <RadarChart data={radarChartData} />
            ) : (
              !isChartsLoading && (
                <div className="flex items-center justify-center h-full">
                  <Text_14_400_B3B3B3>
                    No radar chart data available
                  </Text_14_400_B3B3B3>
                </div>
              )
            )}
          </div>
        </div>

        {/* Heatmap Chart - Full Width with dynamic height */}
        <div
          className="w-full bg-transparent rounded-lg p-6 relative"
          style={{
            height: `${Math.max(400, (heatmapChartData.yAxis.length * 50) + 120)}px`,
            minHeight: "400px",
          }}
        >
          {isChartsLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#0A0A0A]/50 z-10 rounded-lg">
              <Spin size="large" />
            </div>
          )}
          {heatmapChartData.data.length > 0 ? (
            <HeatmapChart data={heatmapChartData} />
          ) : (
            !isChartsLoading && (
              <div className="flex items-center justify-center h-full">
                <Text_14_400_B3B3B3>
                  No heatmap data available
                </Text_14_400_B3B3B3>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
};

export default EvaluationSummary;
