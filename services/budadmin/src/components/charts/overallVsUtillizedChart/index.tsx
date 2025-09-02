// import React, { useEffect, useRef } from 'react';
// import * as echarts from 'echarts';
// import { Box, Text } from '@radix-ui/themes';

// interface OverallVsUtilizedChartProps {
//   data: {
//     categories: string[];
//     series: number[][];
//   };
// }

// const interpolateData = (categories: string[], series: number[][]) => {
//   const interpolatedSeries: number[][] = [];

//   series.forEach((dataArray) => {
//     const interpolatedData: number[] = [];

//     for (let i = 0; i < dataArray.length - 1; i++) {
//       const startValue = dataArray[i];
//       const endValue = dataArray[i + 1];

//       interpolatedData.push(startValue); // Push the existing data point

//       // Calculate 5 interpolated points between each pair of data points
//       for (let j = 1; j <= 5; j++) {
//         const interpolatedValue = startValue + (endValue - startValue) * (j / 6); // Adjust the division here to control the spacing

//         interpolatedData.push(interpolatedValue);
//       }
//     }

//     interpolatedData.push(dataArray[dataArray.length - 1]); // Push the last existing data point
//     interpolatedSeries.push(interpolatedData);
//   });

//   return interpolatedSeries;
// };

// const OverallVsUtilizedChart: React.FC<OverallVsUtilizedChartProps> = ({ data }) => {
//   const chartRef = useRef<HTMLDivElement>(null);

//   useEffect(() => {
//     if (chartRef.current && data.categories.length > 0 && data.series.length > 0) {
//       const myChart = echarts.init(chartRef.current, null, {
//         renderer: 'canvas',
//         useDirtyRect: false,
//       });

//       const interpolatedSeries = interpolateData(data.categories, data.series);

//       const option = {
//         backgroundColor: 'transparent',
//         xAxis: {
//           type: 'category',
//           data: data.categories,
//           axisTick: {
//             show: false,
//           },
//           axisLabel: {
//             color: '#6A6E76',
//             fontSize: 10,
//           },
//           splitLine: {
//             show: false,
//           },
//         },
//         yAxis: {
//           type: 'value',
//           axisLabel: {
//             color: '#6A6E76',
//             fontSize: 10,
//           },
//           splitLine: {
//             lineStyle: {
//               type: 'dashed',
//               color: '#212225',
//             },
//           },
//         },
//         series: interpolatedSeries.map((dataArray) => ({
//           data: dataArray,
//           type: 'line',
//           lineStyle: {
//             color: '#4CA294',
//           },
//           symbol: 'none',
//         })),
//       };

//       myChart.setOption(option);

//       const handleResize = () => {
//         myChart.resize();
//       };

//       window.addEventListener('resize', handleResize);

//       return () => {
//         window.removeEventListener('resize', handleResize);
//         myChart.dispose();
//       };
//     }
//   }, [data]);

//   return (
//     <Box className='relative h-full'>
//       <Text className='block absolute -rotate-90 origin-top-left top-[50%] left-[0rem] mt-[2.5rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>
//         Utilization Percentage
//       </Text>
//       <div ref={chartRef} style={{ width: '100%', height: '105%' }} />
//       <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>
//         Projects
//       </Text>
//     </Box>
//   );
// };

// export default OverallVsUtilizedChart;

import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { Box, Text } from "@radix-ui/themes";

interface OverallVsUtillizedChartProps {
  className?;
  data: any;
}

const OverallVsUtillizedChart: React.FC<OverallVsUtillizedChartProps> = ({
  className = "",
  data,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;
      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("overall Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      const option = {
        backgroundColor: "transparent",
        xAxis: {
          type: "category",
          data: data.categories,
          axisTick: {
            show: false, // Remove the tick marks from the x-axis
          },
          axisLabel: {
            color: "#6A6E76", // Set x-axis label color to white for better visibility
            fontSize: 12,
          },
          splitLine: {
            show: false,
          },
        },
        yAxis: {
          type: "value",
          axisLabel: {
            color: "#6A6E76",
            fontSize: 12,
          },
          splitLine: {
            lineStyle: {
              type: "solid",
              color: "#171717", // Set y-axis split line color to grey
            },
          },
        },
        grid: {
          right: "0%", // Adjust this value to create more space for the legend
          left: "6.5%",
        },
        series: data.series.map((dataArray) => ({
          data: dataArray,
          type: "line",
          smooth: false,
          opacity: 0.8,
          lineStyle: {
            color: "#479D5F", // Line color
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(71, 157, 95, 0.28)" }, // Top color
              { offset: 0.5, color: "rgba(71, 157, 95, 0.1)" }, // Middle color
              { offset: 1, color: "rgba(71, 157, 95, 0)" }, // Bottom color
            ]),
          },
          symbol: "none", // Remove the dots in the data lines
        })),
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
    <Box className={`relative h-full ${className}`}>
      {/* <Text className='block absolute -rotate-90 origin-top-left top-[50%] left-[0.8rem] mt-[2.5rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>
      {data.label1}
      </Text> */}
      <div
        ref={chartRef}
        style={{ width: "100%", height: "100%" }}
        className=""
      />
      {/* <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>
        {data.label2}
      </Text> */}
    </Box>
  );
};

export default OverallVsUtillizedChart;
