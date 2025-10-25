import { Box } from "@radix-ui/themes";
import * as echarts from "echarts";
import React, { useEffect, useRef, useState } from "react";

interface HeatmapChartProps {
  data: {
    xAxis: string[];
    yAxis: string[];
    data: [number, number, number][]; // [x, y, value]
    min?: number;
    max?: number;
    colorRange?: string[];
  };
}

const HeatmapChart: React.FC<HeatmapChartProps> = ({ data }) => {
  const [heatmapData, setHeatmapData] = useState<any>(data);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHeatmapData(data);
  }, [data]);

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

      const option = {
        backgroundColor: "transparent",
        tooltip: {
          position: "top",
          backgroundColor: "rgba(0,0,0,0.75)",
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
          `,
          formatter: (params: any) => {
            return `
              <div style="text-align: left;">
                ${heatmapData.yAxis[params.data[1]]}<br/>
                ${heatmapData.xAxis[params.data[0]]}: ${params.data[2]}
              </div>`;
          },
        },
        grid: {
          left: "5px",
          right: "0%",
          bottom: "10px",
          top: "10px",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          data: heatmapData.xAxis,
          splitArea: {
            show: true,
            areaStyle: {
              color: ["#1A1A1A", "#1F1F1F"],
            },
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            color: "#FFFFFF",
            fontSize: 14,
            fontWeight: 600,
            interval: 0,
            rotate: 0,
          },
        },
        yAxis: {
          type: "category",
          data: heatmapData.yAxis,
          splitArea: {
            show: true,
            areaStyle: {
              color: ["#1A1A1A", "#1F1F1F"],
            },
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            color: "#FFFFFF",
            fontSize: 14,
            fontWeight: 600,
          },
        },
        visualMap: {
          show: false,
          min: heatmapData.min || 0,
          max: heatmapData.max || 100,
          inRange: {
            color: heatmapData.colorRange || [
              "#201C2D", // Dark purple (lowest values)
              "#201C2D",
              "#5B4C81", // Medium purple
              "#5B4C81",
              "#8C73C2", // Light purple (highest values)
              "#8C73C2",
            ],
          },
        },
        series: [
          {
            name: "Heatmap",
            type: "heatmap",
            data: heatmapData.data,
            label: {
              show: true,
              color: "#FFFFFF",
              fontSize: 10,
              fontWeight: 400,
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(126, 87, 194, 0.5)",
              },
            },
            itemStyle: {
              borderRadius: 8,
              borderWidth: 3,
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
  }, [heatmapData]);

  return (
    <Box className="relative h-full w-full">
      <div ref={chartRef} style={{ width: "100%", height: "100%" }} />
    </Box>
  );
};

export default HeatmapChart;
