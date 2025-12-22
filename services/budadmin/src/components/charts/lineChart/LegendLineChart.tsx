import React, { useState, useEffect, useRef } from "react";
import * as echarts from "echarts";
import { Box, Text } from "@radix-ui/themes";
import { AppRequest } from "src/pages/api/requests";
import { Text_12_500_FFFFFF } from "@/components/ui/text";

interface LineChartProps {
  data: {
    categories: any;
    data: any;
    label1?: string;
    label2?: string;
    color?: string;
    smooth?: boolean;
  };
}

const LegendLineChart: React.FC<LineChartProps> = ({ data }) => {
  const [lineChartData, setLineChartData] = useState<any>(data);

  useEffect(() => {
    if (data) {
      setLineChartData(data);
      console.log("lineChartData", data);
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
      const option = {
        backgroundColor: "transparent",
        legend: {
          orient: "horizontal",
          left: "0%",
          top: "top",
          textStyle: {
            color: "#ffffff",
            fontSize: 13,
            fontWeight: 400,
          },
          icon: "square",
          itemWidth: 11,
          itemHeight: 11,
          itemStyle: {
            borderRadius: [5, 5, 5, 5],
          },
        },
        grid: {
          top: lineChartData.label2 ? "32%" : "23%",
          left: "6%",
          bottom: lineChartData.label2 ? "9.5%" : "20%",
          right: "1%",
        },
        xAxis: {
          type: "category",
          data: lineChartData?.data,
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
          data: lineChartData?.categories,
          type: "value",
          // min: 0,
          // max: 80,
          // interval: 20, // Adjust interval to ensure all custom labels are displayed
          axisLabel: {
            formatter: (value: number) => `${value}`,
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
            name: lineChartData.label2 || "",
            color: lineChartData?.color,
            data: lineChartData?.categories,
            type: "line",
            lineStyle: {
              // color: lineChartData?.color,
              width: 1,
            },
            smooth: lineChartData?.smooth,
            showSymbol: false,
          },
          // {
          //     name: 'Task 2',
          //     color: lineChartData?.color,
          //     data: [0, 52, 60, 74, 80, 20, 31],
          //     type: 'line',
          //     lineStyle: {
          //         // color: lineChartData?.color,
          //         width: 1,
          //     },
          //     smooth: lineChartData?.smooth,
          //     showSymbol: false
          // },
          // {
          //     name: 'Task 3',
          //     color: lineChartData?.color,
          //     data: [0, 22, 30, 44, 50, 60, 71],
          //     type: 'line',
          //     lineStyle: {
          //         // color: lineChartData?.color,
          //         width: 1,
          //     },
          //     smooth: lineChartData?.smooth,
          //     showSymbol: false
          // },
        ],
        // tooltip: {
        //     trigger: 'axis',
        //     backgroundColor: 'rgba(44, 44, 44, .6)',
        //     borderWidth: 0,
        //     textStyle: {
        //         color: '#ffffff',
        //         fontSize: 12,
        //     },
        //     padding: 0,
        //     extraCssText: `backdrop-filter: blur(4.2px);border-radius:4px;`,
        //     formatter: (params) => {
        //         const seriesData = params.map(
        //             (item) =>
        //                 `<div style="margin-bottom: 7px;">
        //    <span style="display:inline-block;width:10px;height:10px;background-color:${item.color};margin-right:15px;border-radius:2px;font-size:13px;"></span>
        //    <span style="margin-right: 15px;display:inline-block;min-width:50px;">${item.value[item.seriesName]}%</span>
        //    ${item.seriesName}
        //  </div>`
        //         );
        //         return `<div style="text-align:left; padding: 20px;position:relative;overflow:hidden;">
        //       <img style="position:absolute;bottom:0;right:0;z-index:0;" src="/images/tooltip-pattern.svg"></img>
        //       <div style="font-weight:bold;margin-bottom:10px;font-size:15px;font-weight:600;padding:0 10px;">
        //       <img style="display:inline-block;height:20px;width:20px;margin-right:5px;" src="/images/drawer/cloud.png"></img>
        //       ${params[0].axisValue}</div>
        //       <div style="background-color: #161616;padding: 10px;border-radius:6px;position:relative;z-index:1;">${seriesData.join('')}</div>
        //     </div>`;
        //     },
        //     axisPointer: {
        //         type: 'none', // Disable axis pointer highlight
        //     },
        // },
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
        className="borderbox"
      />
      <Text className="block absolute m-auto bottom-[-1.5rem] left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]">
        {lineChartData?.label2}
      </Text>
    </Box>
  );
};
export default LegendLineChart;
