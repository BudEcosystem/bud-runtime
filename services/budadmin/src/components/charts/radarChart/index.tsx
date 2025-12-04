import { Box } from "@radix-ui/themes";
import * as echarts from "echarts";
import React, { useEffect, useRef, useState } from "react";

/**
 * Converts a color string (hex, rgb, rgba) to rgba format with specified opacity
 */
const colorToRgba = (color: string, opacity: number): string => {
  // Handle rgb and rgba
  if (color.startsWith("rgb")) {
    const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
      return `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${opacity})`;
    }
  }

  // Handle hex colors
  if (color.startsWith("#")) {
    let hex = color.slice(1);
    // Expand shorthand (e.g., #fff -> #ffffff)
    if (hex.length === 3) {
      hex = hex
        .split("")
        .map((c) => c + c)
        .join("");
    }

    if (hex.length === 6) {
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }
  }

  // Fallback for unsupported formats. Log a warning as opacity will not be applied.
  console.warn(`colorToRgba: Unsupported color format "${color}".`);
  return color;
};

interface RadarChartProps {
  data: {
    indicators: { name: string; max: number }[];
    series: {
      name: string;
      value: number[];
      color?: string;
      areaStyle?: any;
    }[];
    showLegend?: boolean;
  };
}

const RadarChart: React.FC<RadarChartProps> = ({ data }) => {
  const [radarChartData, setRadarChartData] = useState<any>(data);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRadarChartData(data);
  }, [data]);

  useEffect(() => {
    if (chartRef.current && radarChartData.indicators?.length > 0) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("Radar Chart container has no width or height yet.");
        return;
      }

      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      const option = {
        backgroundColor: "transparent",
        legend: {
          show: radarChartData.showLegend || false,
          orient: "horizontal",
          left: "center",
          bottom: "0%",
          textStyle: {
            color: "#B3B3B3",
            fontSize: 12,
            fontWeight: 400,
          },
          icon: "rect",
          itemWidth: 12,
          itemHeight: 12,
          itemGap: 20,
        },
        radar: {
          center: ["50%", "50%"],
          radius: "80%",
          startAngle: 90,
          splitNumber: 4,
          shape: "circle",
          axisName: {
            formatter: "{value}",
            color: "#B3B3B3",
            fontSize: 11,
            fontWeight: 400,
          },
          splitLine: {
            lineStyle: {
              color: "#6D6D6D",
              width: 1,
              type: "dashed",
            },
          },
          splitArea: {
            show: false,
          },
          axisLine: {
            lineStyle: {
              color: "#6D6D6D",
              width: 1,
              type: "dashed",
            },
          },
          indicator: radarChartData.indicators,
        },
        tooltip: {
          trigger: "item",
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
            const values = params.value
              .map(
                (val: number, idx: number) =>
                  `${radarChartData.indicators[idx].name}: ${val}`,
              )
              .join("<br/>");
            return `
              <div style="text-align: left;">
                ${params.seriesName}<br/>
                ${values}
              </div>`;
          },
        },
        series: radarChartData.series.map((item: any) => {
          const baseColor = item.color || "#7E57C2";
          return {
            name: item.name,
            type: "radar",
            symbol: "none",
            lineStyle: {
              width: 1,
              color: baseColor,
            },
            areaStyle: item.areaStyle || {
              color: colorToRgba(baseColor, 0.3),
            },
            data: [
              {
                value: item.value,
                name: item.name,
              },
            ],
          };
        }),
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
  }, [radarChartData]);

  return (
    <Box className="relative h-full w-full">
      <div ref={chartRef} style={{ width: "100%", height: "100%" }} />
    </Box>
  );
};

export default RadarChart;
