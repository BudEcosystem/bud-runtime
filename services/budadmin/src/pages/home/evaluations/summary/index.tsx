"use client";
import { useState, useEffect, useMemo, useCallback } from "react";
import React from "react";
import { Image } from "antd";
import {
  Text_10_400_757575,
  Text_10_400_B3B3B3,
  Text_10_400_D1B854,
  Text_10_400_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_500_FFFFFF,
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
} from "../../../../components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useRouter } from "next/router";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useEvaluations, GetEvaluationsPayload, Evaluation } from "src/hooks/useEvaluations";
import RadarChart from "@/components/charts/radarChart";
import HeatmapChart from "@/components/charts/heatmapChart";
import * as echarts from 'echarts';

const EvaluationSumary = () => {
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]);
  const [selectedTrait, setSelectedTrait] = useState<string | null>(null);
  const [selectedDeployments, setSelectedDeployments] = useState<number[]>([1, 3]);
  const { getEvaluations, evaluationsList, evaluationsListTotal, getTraits, traitsList } = useEvaluations();
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");

  // Mock data for charts - replace with real data when available
  const deployments = [
    { id: 1, name: "Deployment 1", status: "active", color: "#22C55E" },
    { id: 2, name: "Deployment 2", status: "inactive", color: "#A855F7" },
    { id: 3, name: "Deployment 3", status: "active", color: "#3B82F6" },
  ];

  const traits = [
    "Trait 1", "Trait 2", "Trait 3", "Trait 4"
  ];

  // Generate radar chart data based on selected deployments
  const radarChartData = {
    indicators: [
      { name: "Trait 1", max: 1 },
      { name: "Trait 2", max: 1 },
      { name: "Trait 3", max: 1 },
      { name: "Trait 4", max: 1 },
      { name: "Trait 5", max: 1 },
      { name: "Trait 6", max: 1 },
    ],
    series: deployments
      .filter(deployment => selectedDeployments.includes(deployment.id))
      .map(deployment => ({
        name: deployment.name,
        value: deployment.id === 1 
          ? [0.8, 0.7, 0.9, 0.6, 0.85, 0.75]
          : deployment.id === 2
          ? [0.6, 0.8, 0.7, 0.9, 0.65, 0.8]
          : [0.9, 0.6, 0.8, 0.7, 0.9, 0.85],
        color: deployment.color,
        areaStyle: {
          color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
            { 
              color: deployment.color + '66', // 40% opacity in hex
              offset: 0 
            },
            { 
              color: deployment.color + '1A', // 10% opacity in hex
              offset: 1 
            },
          ]),
        },
      })),
    showLegend: false,
  };

  const heatmapChartData = {
    xAxis: ["MMLU", "ARC", "MMLU", "MMLU", "MMLU", "MMLU", "MMLU", "MMLU", "MMLU", "MMLU", "MMLU", "MMLU"],
    yAxis: ["Model 5", "Model 4", "Model 3", "Model 2", "Model 1"],
    data: [
      // Model 5
      [0, 0, 19.8] as [number, number, number], [1, 0, 19.7] as [number, number, number], [2, 0, 25.0] as [number, number, number], [3, 0, 30.3] as [number, number, number], [4, 0, 33.4] as [number, number, number], [5, 0, 36.3] as [number, number, number], 
      [6, 0, 38.2] as [number, number, number], [7, 0, 39.3] as [number, number, number], [8, 0, 34.0] as [number, number, number], [9, 0, 30.0] as [number, number, number], [10, 0, 21.3] as [number, number, number], [11, 0, 17.9] as [number, number, number],
      // Model 4
      [0, 1, 2.7] as [number, number, number], [1, 1, 5.1] as [number, number, number], [2, 1, 10.3] as [number, number, number], [3, 1, 16.7] as [number, number, number], [4, 1, 21.8] as [number, number, number], [5, 1, 24.9] as [number, number, number], 
      [6, 1, 27.5] as [number, number, number], [7, 1, 27.0] as [number, number, number], [8, 1, 21.7] as [number, number, number], [9, 1, 15.6] as [number, number, number], [10, 1, 8.2] as [number, number, number], [11, 1, 3.3] as [number, number, number],
      // Model 3
      [0, 2, -0.4] as [number, number, number], [1, 2, 1.2] as [number, number, number], [2, 2, 5.5] as [number, number, number], [3, 2, 11.0] as [number, number, number], [4, 2, 16.0] as [number, number, number], [5, 2, 19.1] as [number, number, number], 
      [6, 2, 21.3] as [number, number, number], [7, 2, 20.7] as [number, number, number], [8, 2, 15.9] as [number, number, number], [9, 2, 10.4] as [number, number, number], [10, 2, 4.9] as [number, number, number], [11, 2, 0.7] as [number, number, number],
      // Model 2
      [0, 3, -3.4] as [number, number, number], [1, 3, -2.3] as [number, number, number], [2, 3, 1.3] as [number, number, number], [3, 3, 5.4] as [number, number, number], [4, 3, 10.2] as [number, number, number], [5, 3, 13.4] as [number, number, number], 
      [6, 3, 15.4] as [number, number, number], [7, 3, 15.0] as [number, number, number], [8, 3, 11.0] as [number, number, number], [9, 3, 6.1] as [number, number, number], [10, 3, 1.8] as [number, number, number], [11, 3, -1.9] as [number, number, number],
      // Model 1
      [0, 4, -24.6] as [number, number, number], [1, 4, -20.0] as [number, number, number], [2, 4, -15.1] as [number, number, number], [3, 4, -4.4] as [number, number, number], [4, 4, -2.0] as [number, number, number], [5, 4, 3.0] as [number, number, number], 
      [6, 4, 7.0] as [number, number, number], [7, 4, 5.0] as [number, number, number], [8, 4, -2.0] as [number, number, number], [9, 4, -8.0] as [number, number, number], [10, 4, -12.0] as [number, number, number], [11, 4, -20.0] as [number, number, number],
    ] as [number, number, number][],
    min: -30,
    max: 40,
  };

  const handleFilterToggle = useCallback((filterName: string) => {
    setSelectedFilters(prev => {
      if (prev.includes(filterName)) {
        return prev.filter(f => f !== filterName);
      } else {
        return [...prev, filterName];
      }
    });
  }, []);

  const handleTraitClick = useCallback((trait: string) => {
    setSelectedTrait(selectedTrait === trait ? null : trait);
  }, [selectedTrait]);

  const handleDeploymentToggle = useCallback((deploymentId: number) => {
    setSelectedDeployments(prev => {
      if (prev.includes(deploymentId)) {
        return prev.filter(id => id !== deploymentId);
      } else {
        return [...prev, deploymentId];
      }
    });
  }, []);

  useEffect(() => {
    const fetchEvaluations = async () => {
      const payload: GetEvaluationsPayload = {
        page: 1,
        limit: 500,
        name: searchValue,
      };
      await getEvaluations(payload);
    };
    fetchEvaluations();
  }, [searchValue, getEvaluations]);

  useEffect(() => {
    getTraits()
  }, []);

  return (
    <div className="w-full h-full overflow-y-auto">
      <div className="flex flex-col gap-6 p-6">
        {/* Top Section - Sidebar and Radar Chart */}
        <div className="flex gap-6">
          {/* Left Section - Following Figma specs */}
          <div className="w-[254px] flex-shrink-0">
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-[12px] p-4 flex flex-col gap-6">
          {/* Search Section */}
          <div className="bg-[rgba(255,255,255,0.03)] rounded-[8px] h-[2.125rem] flex items-center px-[10px]">
            <div className="flex items-center gap-3 w-full">
              <div className="w-[14px] h-[14px] opacity-50">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="5.5" cy="5.5" r="4.5" stroke="#B3B3B3" strokeWidth="1.2"/>
                  <path d="M9 9L12 12" stroke="#B3B3B3" strokeWidth="1.2" strokeLinecap="round"/>
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
              <Text_14_400_B3B3B3 className="text-[14px] leading-[20px] font-normal">Deployments</Text_14_400_B3B3B3>
            </div>
            <div className="flex flex-col gap-1">
              {deployments.map((deployment) => {
                const isSelected = selectedDeployments.includes(deployment.id);
                return (
                  <div
                    key={deployment.id}
                    className={`flex items-center gap-2 py-[8px] px-[10px] rounded-[8px] cursor-pointer transition-all ${
                      isSelected 
                        ? 'bg-[rgba(255,255,255,0.03)]' 
                        : 'hover:bg-[rgba(255,255,255,0.02)]'
                    }`}
                    onClick={() => handleDeploymentToggle(deployment.id)}
                  >
                    <div className="w-5 h-5 rounded-[6px] bg-cover bg-center bg-[#1F1F1F]" />
                    <div className="flex-1">
                      <Text_14_400_EEEEEE className="text-[14px] leading-[19px]">
                        {deployment.name}
                      </Text_14_400_EEEEEE>
                    </div>
                    <div 
                      className="w-2 h-2 rounded-full" 
                      style={{ backgroundColor: deployment.color }}
                    />
                    <div className="w-3 h-3 opacity-0 hover:opacity-100 transition-opacity">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <circle cx="6" cy="2" r="1" fill="#B3B3B3"/>
                        <circle cx="6" cy="6" r="1" fill="#B3B3B3"/>
                        <circle cx="6" cy="10" r="1" fill="#B3B3B3"/>
                      </svg>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Traits Section */}
          <div className="flex flex-col gap-3">
            <div className="px-2">
              <Text_14_400_B3B3B3 className="text-[14px] leading-[20px] font-normal">Traits</Text_14_400_B3B3B3>
            </div>
            <div className="flex flex-col gap-1">
              {traits.map((trait) => (
                <div
                  key={trait}
                  className={`flex items-center gap-2 py-[8px] px-[10px] rounded-[8px] cursor-pointer transition-all ${
                    selectedTrait === trait 
                      ? 'bg-[rgba(255,255,255,0.03)]' 
                      : 'hover:bg-[rgba(255,255,255,0.02)]'
                  }`}
                  onClick={() => handleTraitClick(trait)}
                >
                  <div className="w-5 h-5 rounded-[6px] bg-[rgba(255,255,255,0.1)]" />
                  <div className="flex-1">
                    <Text_14_400_EEEEEE className="text-[14px] leading-[19px]">
                      {trait}
                    </Text_14_400_EEEEEE>
                  </div>
                </div>
              ))}
            </div>
          </div>
            </div>
          </div>

          {/* Radar Chart */}
          <div className="flex-1 h-[500px] bg-transparent rounded-lg p-6">
            <RadarChart data={radarChartData} />
          </div>
        </div>

        {/* Heatmap Chart - Full Width */}
        <div className="w-full h-[400px] bg-transparent rounded-lg p-6">
          <HeatmapChart data={heatmapChartData} />
        </div>
      </div>
    </div>
  );
};

export default EvaluationSumary;
