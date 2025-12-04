import { Box } from "@radix-ui/themes";
import * as echarts from "echarts";
import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";

interface HeatmapChartProps {
  data: {
    xAxis: string[];
    yAxis: string[];
    data: [number, number, number][]; // [x, y, value]
    min?: number;
    max?: number;
    colorRange?: string[];
  };
  minCellWidth?: number; // Minimum width for each cell in pixels
  minCellHeight?: number; // Minimum height for each cell in pixels
}

// Chevron Right Icon
const ChevronRight = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M9 18L15 12L9 6"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// Chevron Left Icon
const ChevronLeft = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M15 18L9 12L15 6"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const HeatmapChart: React.FC<HeatmapChartProps> = ({
  data,
  minCellWidth = 70,
  minCellHeight = 50
}) => {
  const [heatmapData, setHeatmapData] = useState<any>(data);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHeatmapData(data);
  }, [data]);

  // Calculate required dimensions based on data
  const chartDimensions = useMemo(() => {
    const xCount = heatmapData.xAxis?.length || 0;
    const yCount = heatmapData.yAxis?.length || 0;

    // Calculate minimum required width and height
    const yAxisLabelWidth = 120; // Space for y-axis labels
    const xAxisLabelHeight = 80; // Space for rotated x-axis labels
    const padding = 40; // Additional padding

    const minWidth = Math.max(600, (xCount * minCellWidth) + yAxisLabelWidth + padding);
    const minHeight = Math.max(300, (yCount * minCellHeight) + xAxisLabelHeight + padding);

    return { minWidth, minHeight, xCount, yCount };
  }, [heatmapData.xAxis, heatmapData.yAxis, minCellWidth, minCellHeight]);

  // Determine if we need horizontal scroll
  const needsHorizontalScroll = chartDimensions.xCount > 10;

  // Check scroll position and update indicators
  const updateScrollIndicators = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container || !needsHorizontalScroll) {
      setCanScrollLeft(false);
      setCanScrollRight(false);
      return;
    }

    const { scrollLeft, scrollWidth, clientWidth } = container;
    const scrollThreshold = 5; // Small threshold to account for rounding

    setCanScrollLeft(scrollLeft > scrollThreshold);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - scrollThreshold);
  }, [needsHorizontalScroll]);

  // Initialize scroll indicators after chart renders
  useEffect(() => {
    // Small delay to ensure container has proper dimensions
    const timer = setTimeout(() => {
      updateScrollIndicators();
    }, 100);

    return () => clearTimeout(timer);
  }, [heatmapData, chartDimensions, updateScrollIndicators]);

  // Scroll handlers
  const scrollLeft = useCallback(() => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollBy({
        left: -300,
        behavior: "smooth"
      });
    }
  }, []);

  const scrollRight = useCallback(() => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollBy({
        left: 300,
        behavior: "smooth"
      });
    }
  }, []);

  useEffect(() => {
    if (chartRef.current && heatmapData.data?.length > 0) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("Heatmap Chart container has no width or height yet.");
        return;
      }

      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      const labelFontSize = chartDimensions.xCount > 15 ? 10 : 12;

      // Calculate cell dimensions
      const effectiveWidth = Math.max(containerWidth, chartDimensions.minWidth);
      const cellWidth = (effectiveWidth - 150) / chartDimensions.xCount;
      const showLabelsInCells = cellWidth >= 40;

      // Truncate label helper
      const truncateLabel = (label: string, maxLength: number) => {
        if (label.length <= maxLength) return label;
        return label.substring(0, maxLength - 2) + '..';
      };

      // Calculate max characters based on cell width
      const maxLabelChars = Math.max(4, Math.floor((minCellWidth - 10) / 7));

      const option = {
        backgroundColor: "transparent",
        tooltip: {
          // Dynamic position to avoid cut-off at edges
          position: function (point: number[], params: any, dom: HTMLElement, rect: any, size: any) {
            const tooltipHeight = size.contentSize[1];
            const tooltipWidth = size.contentSize[0];
            const chartWidth = size.viewSize[0];

            let x = point[0] - tooltipWidth / 2;
            let y = point[1] - tooltipHeight - 10;

            // If tooltip would be cut off at top, show it below the point
            if (y < 0) {
              y = point[1] + 20;
            }

            // Keep tooltip within horizontal bounds
            if (x < 0) {
              x = 5;
            } else if (x + tooltipWidth > chartWidth) {
              x = chartWidth - tooltipWidth - 5;
            }

            return [x, y];
          },
          backgroundColor: "rgba(0,0,0,0.85)",
          borderColor: "#1F1F1F",
          borderWidth: 1,
          textStyle: {
            color: "#EEEEEE",
            fontSize: 12,
            fontWeight: 400,
          },
          extraCssText: `
            backdrop-filter: blur(10px);
            border-radius: 4px;
            z-index: 9999;
            max-width: 300px;
          `,
          confine: true, // Keep tooltip within chart container
          formatter: (params: any) => {
            const value = params.data[2];
            const displayValue = value !== null && value !== undefined
              ? (typeof value === 'number' ? value.toFixed(2) : value)
              : 'N/A';
            return `
              <div style="text-align: left;">
                <strong>${heatmapData.yAxis[params.data[1]]}</strong><br/>
                ${heatmapData.xAxis[params.data[0]]}: <span style="color: #8C73C2; font-weight: 600;">${displayValue}</span>
              </div>`;
          },
        },
        grid: {
          left: "10px",
          right: "20px",
          bottom: "40px",
          top: "10px",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          data: heatmapData.xAxis,
          splitArea: {
            show: false,
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            color: "#B3B3B3",
            fontSize: labelFontSize,
            fontWeight: 500,
            interval: 0,
            rotate: 0,
            formatter: (value: string) => truncateLabel(value, maxLabelChars),
          },
          triggerEvent: true, // Enable events for axis labels
          axisPointer: {
            show: true,
            type: "shadow",
            label: {
              show: true,
              backgroundColor: "rgba(0,0,0,0.9)",
              color: "#EEEEEE",
              fontSize: 12,
              padding: [6, 10],
              borderRadius: 4,
              formatter: (params: any) => params.value, // Show full label
            },
          },
        },
        yAxis: {
          type: "category",
          data: heatmapData.yAxis,
          splitArea: {
            show: false,
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            color: "#B3B3B3",
            fontSize: 12,
            fontWeight: 500,
            overflow: "truncate",
            width: 100,
          },
        },
        visualMap: {
          show: true,
          min: heatmapData.min || 0,
          max: heatmapData.max || 100,
          orient: "horizontal",
          left: "center",
          bottom: "0px",
          itemWidth: 20,
          itemHeight: 10,
          textStyle: {
            color: "#B3B3B3",
            fontSize: 10,
          },
          inRange: {
            color: heatmapData.colorRange || [
              "#1a1625", // Dark (lowest values)
              "#2d2347",
              "#4a3a6e",
              "#6b5295",
              "#8C73C2", // Light purple (highest values)
            ],
          },
        },
        series: [
          {
            name: "Heatmap",
            type: "heatmap",
            data: heatmapData.data,
            label: {
              show: showLabelsInCells,
              color: "#FFFFFF",
              fontSize: cellWidth > 60 ? 11 : 9,
              fontWeight: 500,
              formatter: (params: any) => {
                const value = params.data[2];
                if (value === null || value === undefined || value === 0) {
                  return '';
                }
                return typeof value === 'number' ? value.toFixed(1) : value;
              },
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(126, 87, 194, 0.5)",
              },
            },
            itemStyle: {
              borderRadius: 4,
              borderWidth: 2,
              borderColor: "#0A0A0A",
            },
          },
        ],
      };

      myChart.setOption(option);

      const handleResize = () => {
        myChart.resize();
      };

      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        myChart.dispose();
      };
    }
  }, [heatmapData, chartDimensions, minCellWidth]);

  return (
    <Box className="relative h-full w-full">
      {/* Scrollable container */}
      <div
        ref={scrollContainerRef}
        className="h-full w-full"
        style={{
          overflowX: needsHorizontalScroll ? "auto" : "hidden",
          overflowY: "hidden",
          scrollbarWidth: "thin",
          scrollbarColor: "#4a4a4a #1a1a1a",
        }}
        onScroll={updateScrollIndicators}
      >
        <div
          ref={chartRef}
          style={{
            width: needsHorizontalScroll ? `${chartDimensions.minWidth}px` : "100%",
            height: "100%",
            minWidth: needsHorizontalScroll ? `${chartDimensions.minWidth}px` : undefined,
          }}
        />
      </div>

      {/* Left scroll indicator */}
      {needsHorizontalScroll && canScrollLeft && (
        <div
          className="absolute left-0 top-0 h-full flex items-center cursor-pointer z-10 transition-opacity duration-200"
          onClick={scrollLeft}
          style={{
            background: "linear-gradient(to right, rgba(10, 10, 10, 0.95) 0%, rgba(10, 10, 10, 0.8) 40%, rgba(10, 10, 10, 0) 100%)",
            width: "60px",
            paddingLeft: "8px",
          }}
        >
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#1F1F1F] hover:bg-[#2a2a2a] text-[#B3B3B3] hover:text-white transition-colors border border-[#333]">
            <ChevronLeft />
          </div>
        </div>
      )}

      {/* Right scroll indicator */}
      {needsHorizontalScroll && canScrollRight && (
        <div
          className="absolute right-0 top-0 h-full flex items-center justify-end cursor-pointer z-10 transition-opacity duration-200"
          onClick={scrollRight}
          style={{
            background: "linear-gradient(to left, rgba(10, 10, 10, 0.95) 0%, rgba(10, 10, 10, 0.8) 40%, rgba(10, 10, 10, 0) 100%)",
            width: "60px",
            paddingRight: "8px",
          }}
        >
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#1F1F1F] hover:bg-[#2a2a2a] text-[#B3B3B3] hover:text-white transition-colors border border-[#333]">
            <ChevronRight />
          </div>
        </div>
      )}
    </Box>
  );
};

export default HeatmapChart;
