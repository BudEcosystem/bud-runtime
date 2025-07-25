import { Text_12_500_FFFFFF } from '@/components/ui/text';
import { Box, Text } from '@radix-ui/themes';
import * as echarts from 'echarts';
import React, { useEffect, useRef, useState } from 'react';
import { AppRequest } from 'src/pages/api/requests';

interface ScatterChartProps {
  data: {
    categories: string[];
    data: [];
    label1: string;
    label2: string;
    barColor?: string
  };
}

const ScatterChart: React.FC<ScatterChartProps> = ({ data }) => {
  const [chartData, setBarChartData] = useState<any>(data);

  useEffect(() => {
    if (data) { setBarChartData(data); }
  }, [data]);
  
  useEffect(() => {
    console.log('chartData', chartData);
  }, [chartData]);
  
  const chartRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("bar Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: 'canvas',
        useDirtyRect: false,
      });

      const option = {
        backgroundColor: 'transparent',
        grid: {
          left: "10%",
          right: "6%",
          bottom: '20%',
          top: "23%"
        },
        xAxis: {
          scale: true,
          min: 0, 
          type: '',
          axisTick: {
            show: false, // Remove the tick marks from the x-axis
          },
          splitLine: {
            show: false,    // Disable horizontal grid lines
          },
          axisLabel: {
            color: '#6A6E76', // Set x-axis label color to white for better visibility
            fontSize: 13,
            fontWeight: 300,
          },
        },
        yAxis: {
          scale: true,
          min: 0,           // Set minimum value
          // max: 80,          // Set maximum value
          // interval: 20,     // Set interval between ticks
          axisTick: {
            show: false,
          },
          offset: 0,
          axisLabel: {
            color: '#EEEEEE', // Set x-axis label color to white for better visibility
            fontSize: 13,
            fontWeight: 300,
          },
          axisLine: {
            show: false,
            lineStyle: {
              color: '#757575', // Set y-axis line color to white for better visibility
              fontSize: 8,
            },
          },
          splitLine: {
            lineStyle: {
              type: 'solid',
              color: '#171717', // Set y-axis split line color to grey
            },
          },
        },
        series: [
          // {
          //   type: 'scatter',
          //   symbolSize: 8,
          //   // Use category names (or corresponding indices) as the x values
          //   // Here we simply provide the labels in order; alternatively, you could use indices
          //   data: [
          //     // ["Model 1", 51.6],
          //     // ["Model 2", 59.0],
          //     // ["Model 3", 49.2],
          //     // ["Model 4", 63.0],
          //     // ["Model 5", 78.6],
          //   ],
          // },
          {
            type: 'scatter',
            symbolSize: 8,
            itemStyle: {
              color: '#9462D5'
            },
            data: [
              ...chartData?.data,
              // [10.0, 8.04],
              // [8.07, 6.95],
            ],
          }
        ]
      };

      myChart.setOption(option);

      const handleResize = () => {
        myChart.resize();
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        myChart.dispose();
      };
    }
  }, [chartData]);

  return (
    <Box className='relative h-full'>
      {/* <Text_12_500_FFFFFF className='block absolute top-[1.8em] left-[5em]'>{chartData?.title}</Text_12_500_FFFFFF> */}
      <Text className='block absolute -rotate-90 origin-top-left	 top-[50%] left-[0rem] mt-[2.5rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{chartData?.label1}</Text>
      <div ref={chartRef} style={{ width: '100%', height: '100%' }} className='' />
      <Text className='block absolute m-auto bottom-[-.5rem] left-[40%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{chartData?.label2}</Text>
    </Box>
  );
};

export default ScatterChart;


