import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { Box, Text } from '@radix-ui/themes';

interface RegularBarChartProps {
  data: {
    categories: string[];
    data: number[];
    label1: string;
    label2: string;
  };
}

const RegularBarChart: React.FC<RegularBarChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTimeout(() => {
      if (chartRef.current) {
        const containerWidth = chartRef.current.clientWidth;
        const containerHeight = chartRef.current.clientHeight;

        if (containerWidth === 0 || containerHeight === 0) {
          console.warn(" regular Chart container has no width or height yet.");
          return;
        }
        const myChart = echarts.init(chartRef.current, null, {
          renderer: 'canvas',
          useDirtyRect: false,
        });

        const option = {
          backgroundColor: 'transparent',
          xAxis: {
            type: 'category',
            data: data?.categories,
            axisTick: {
              show: false, // Remove the tick marks from the x-axis
            },
            axisLabel: {
              color: '#6A6E76', // Set x-axis label color to white for better visibility
              fontSize: 10,
              formatter: (value: string) => {
                const maxLength = 5;
                return value.length > maxLength ? value.slice(0, maxLength) + '...' : value;
              },
            },
          },
          yAxis: {
            splitLine: {
              lineStyle: {
                type: 'dashed',
                color: '#212225', // Set y-axis split line color to grey
              },
            },
            axisLine: {
              lineStyle: {
                color: '#6A6E76', // Set y-axis line color to white for better visibility
              },
            },
          },
          series: [
            {
              data: data?.data?.map((value, index) => ({
                value,
                itemStyle: {
                  borderRadius: [5, 5, 0, 0], // Top-left and top-right corners rounded
                  color: index % 2 === 0 ? '#3F8EF7' : '#D45453',
                },
              })),
              type: 'bar',
              barWidth: 22, // Set the width of the bars
              barGap: '0%', // Set the space between bars to 0
            },
          ],
          tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(0,0,0,.75)',
            borderColor: '#1F1F1F',
            borderWidth: 1,
            textStyle: {
              color: '#EEEEEE',
              fontSize: 12,
              fontWeight: 400
            },
            extraCssText: `backdrop-filter: blur(10px);border-radius:4px;`,
            formatter: (params) => {
              return `
                <div style="text-align: left;text-transform: capitalize">
                  ${params.name}<br/>
                  ${params.value}<br/>
                </div>`;
            },
          },
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
    }, 100)
  }, [data]);

  return (
    <Box className='relative h-full'>
      <Text className='block absolute -rotate-90 origin-top-left	 top-[50%] left-[.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{data?.label1}</Text>
      <div ref={chartRef} style={{ width: '100%', height: '105%' }} className='pl-[.7rem] borderbox' />
      <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{data?.label2}</Text>
    </Box>
  );
};

export default RegularBarChart;
