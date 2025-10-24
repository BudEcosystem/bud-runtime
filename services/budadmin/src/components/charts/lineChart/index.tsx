import React, { useState, useEffect, useRef } from "react";
import * as echarts from "echarts";
import { Box, Text } from "@radix-ui/themes";
import { AppRequest } from "src/pages/api/requests";
import { Text_12_500_FFFFFF } from "@/components/ui/text";

interface LineChartProps {
  data: {
    categories: string[];
    data: number[];
    label1?: string;
    label2?: string;
    color?: string;
    smooth?: boolean;
    yAxisUnit?: string; // Unit to display on Y-axis (e.g., "%", "Mbps", "GB")
    yAxisAutoScale?: boolean; // If true, auto-scale Y-axis based on data
    yAxisMin?: number; // Minimum Y-axis value (ignored if yAxisAutoScale is true)
    yAxisMax?: number; // Maximum Y-axis value (ignored if yAxisAutoScale is true)
    yAxisInterval?: number; // Y-axis interval (ignored if yAxisAutoScale is true)
  };
}

const LineChart: React.FC<LineChartProps> = ({ data }) => {
  const [lineChartData, setLineChartData] = useState<any>(data);

  useEffect(() => {
    if (data) {
      setLineChartData(data);
    }
  }, [data]);

  const chartRef = useRef<HTMLDivElement>(null);
  // const [lineChartProps, setLineChartProps] = useState(data);

  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("line Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      // Calculate Y-axis range if auto-scale is enabled
      let yAxisMin = lineChartData?.yAxisMin ?? 0;
      let yAxisMax = lineChartData?.yAxisMax ?? 80;
      let yAxisInterval = lineChartData?.yAxisInterval ?? 20;

      if (lineChartData?.yAxisAutoScale && lineChartData?.data?.length > 0) {
        const dataValues = lineChartData.data;
        const minValue = Math.min(...dataValues);
        const maxValue = Math.max(...dataValues);

        // Add 10% padding to top and bottom for better visualization
        const range = maxValue - minValue;
        const padding = range * 0.1;
        yAxisMin = Math.max(0, Math.floor(minValue - padding));
        yAxisMax = Math.ceil(maxValue + padding);

        // Calculate a nice interval (roughly 4-5 ticks)
        const roughInterval = (yAxisMax - yAxisMin) / 4;
        // Round to nearest "nice" number (1, 2, 5, 10, 20, 50, etc.)
        const magnitude = Math.pow(10, Math.floor(Math.log10(roughInterval)));
        const normalizedInterval = roughInterval / magnitude;
        if (normalizedInterval <= 1) yAxisInterval = magnitude;
        else if (normalizedInterval <= 2) yAxisInterval = 2 * magnitude;
        else if (normalizedInterval <= 5) yAxisInterval = 5 * magnitude;
        else yAxisInterval = 10 * magnitude;
      }

      const yAxisUnit = lineChartData?.yAxisUnit ?? "%";

      const option = {
        backgroundColor: "transparent",
        grid: {
          top: "23%",
          left: "0%",
          bottom: "1%",
          right: "0%",
          containLabel: true,
        },
        xAxis: {
          type: "category",
          data: lineChartData?.categories,
          axisTick: {
            show: false, // Remove the tick marks from the x-axis
          },
          axisLabel: {
            color: "#B3B3B3", // Set x-axis label color to white for better visibility
            fontSize: 13,
            fontWeight: 300,
          },
          splitLine: {
            show: false,
          },
        },
        yAxis: {
          type: "value",
          min: yAxisMin,
          max: yAxisMax,
          interval: yAxisInterval,
          axisLabel: {
            formatter: (value: number) => `${value}${yAxisUnit}`,
            color: "#EEEEEE",
            fontSize: 13,
            fontWeight: 300,
          },
          splitLine: {
            lineStyle: {
              type: "solid",
              color: "#171717", // Set y-axis split line color to grey
            },
          },
        },
        series: [
          {
            color: lineChartData?.color,
            data: lineChartData?.data?.map((value, index) => ({
              value,
              itemStyle: {
                borderRadius: [5, 5, 0, 0], // Top-left and top-right corners rounded
                color: index % 2 === 0 ? "#3F8EF7" : "#D45453",
              },
            })),
            type: "line",
            lineStyle: {
              color: lineChartData?.color,
              width: 1,
            },
            smooth: lineChartData?.smooth,
            showSymbol: false,
          },
        ],
        tooltip: {
          trigger: "axis",
        },
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
  }, [lineChartData]);

  return (
    <Box height="150px" className="relative h-full ">
      <Text_12_500_FFFFFF className="block absolute top-[1.8em] left-[5em]">
        {lineChartData?.title}
      </Text_12_500_FFFFFF>
      <Text className="block absolute -rotate-90 origin-top-left	 top-[50%] left-[.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]">
        {lineChartData?.label1}
      </Text>
      <div
        ref={chartRef}
        style={{ width: "100%", height: "100%" }}
        className="pl-[.7rem] borderbox"
      />
      <Text className="block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]">
        {lineChartData?.label2}
      </Text>
    </Box>
  );
};
export default LineChart;
