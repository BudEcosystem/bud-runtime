import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { Box } from "@radix-ui/themes";

interface BenchmarkChartProps {
  data: {
    dimensions: string[];
    source: Array<{ [key: string]: number | string }>;
  };
}

const BenchmarkChart: React.FC<BenchmarkChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    console.log("BenchmarkChart data", data);
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("Benchmark Chart container has no width or height yet.");
        return;
      }

      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      const formatLegendText = (text: string) => {
        const labelMap: Record<string, string> = {
          avg_ttft: "Mean TTFT",
          avg_tpot: "Mean TPOT",
          avg_latency: "Mean Latency",
          avg_output_len: "Mean Output Length",
        };
        return labelMap[text] || text.replace(/[^a-zA-Z0-9]/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
      };

      const option = {
        backgroundColor: "transparent",
        legend: {
          show: true,
          orient: "horizontal",
          left: "0%",
          top: "0",
          textStyle: {
            color: "#ffffff",
            fontSize: 13,
            fontWeight: 400,
          },
          icon: "roundRect",
          itemWidth: 11,
          itemHeight: 11,
          itemStyle: {
            borderRadius: [5, 5, 5, 5],
          },
          formatter: formatLegendText,
        },
        grid: {
          right: "1%",
          left: "6%",
          top: "32%",
          bottom: "9.5%",
        },
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(44, 44, 44, .6)",
          borderWidth: 0,
          textStyle: {
            color: "#ffffff",
            fontSize: 12,
          },
          padding: 0,
          extraCssText: `backdrop-filter: blur(4.2px);border-radius:4px;`,
          formatter: (params) => {
            const seriesData = params.map(
              (item) =>
                `<div style="margin-bottom: 7px;">
                   <span style="display:inline-block;width:10px;height:10px;background-color:${item.color};margin-right:15px;border-radius:2px;font-size:13px;"></span>
                   <span style="margin-right: 15px;display:inline-block;min-width:50px;">${item.value[item.seriesName]}s</span>
                   ${item.seriesName}
                 </div>`,
            );
            return `<div style="text-align:left; padding: 20px;position:relative;overflow:hidden;">
                      <img style="position:absolute;bottom:0;right:0;z-index:0;" src="/images/tooltip-pattern.svg"></img>
                      <div style="font-weight:bold;margin-bottom:10px;font-size:15px;font-weight:600;padding:0 10px;">
                      <img style="display:inline-block;height:20px;width:20px;margin-right:5px;" src="/images/drawer/cloud.png"></img>
                      ${params[0].axisValue}</div>
                      <div style="background-color: #161616;padding: 10px;border-radius:6px;position:relative;z-index:1;">${seriesData.join("")}</div>
                    </div>`;
          },
          axisPointer: {
            type: "none", // Disable axis pointer highlight
          },
        },
        dataset: {
          dimensions: data.dimensions,
          source: data.source,
        },
        xAxis: {
          type: "category",

          axisLine: {
            lineStyle: {
              color: "#2d2d2d",
            },
          },
          axisLabel: {
            color: "#6A6E76",
            fontSize: 13,
            fontWeight: 300,
          },
          axisTick: {
            show: false,
          },
        },
        yAxis: {
          splitLine: {
            lineStyle: {
              type: "solid",
              color: "#171717",
            },
          },
          axisLine: {
            lineStyle: {
              color: "#2d2d2d",
            },
          },
          axisLabel: {
            color: "#6A6E76",
            fontSize: 12,
            fontWeight: 300,
          },
        },
        // Generate series dynamically based on dimensions (excluding 'product' which is x-axis)
        series: (() => {
          const colors = ["#FF895E", "#479D5F", "#4077E6", "#D1B854"];
          const metricDimensions = data.dimensions.filter(d => d !== "product");
          return metricDimensions.map((_, index) => ({
            type: "line",
            smooth: true,
            symbol: "circle",
            symbolSize: 6,
            lineStyle: {
              width: 2,
              color: colors[index % colors.length],
            },
            itemStyle: {
              color: colors[index % colors.length],
            },
            areaStyle: {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: colors[index % colors.length] + "40" },
                  { offset: 1, color: colors[index % colors.length] + "05" },
                ],
              },
            },
          }));
        })(),
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
  }, [data]);

  return (
    <Box className="relative h-full">
      <div ref={chartRef} style={{ width: "100%", height: "100%" }} />
    </Box>
  );
};

export default BenchmarkChart;
