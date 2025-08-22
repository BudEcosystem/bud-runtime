import { Text_12_500_FFFFFF } from '@/components/ui/text';
import { Box, Text } from '@radix-ui/themes';
import * as echarts from 'echarts';
import React, { useEffect, useRef, useState } from 'react';
import { AppRequest } from '@/services/api/requests';

interface BarChartProps {
  data: {
    categories: any[];
    data: any[];
    label1?: string;
    label2?: string;
    barColor?: string
    showLegend?: string
  };
}

const BarChart: React.FC<BarChartProps> = ({ data }) => {
  const [barChartData, setBarChartData] = useState<any>(data);

  useEffect(() => {
    setBarChartData(data);
  }, [data]);

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
      const formatLegendText = (text: string) => {
        return text
          .replace(/[^a-zA-Z0-9]/g, ' ')
          .replace(/\b\w/g, char => char.toUpperCase());
      };

      const option = {
        legend: {
          show: barChartData.showLegend || false,
          orient: 'horizontal',
          left: '0%',
          top: 'top',
          textStyle: {
            color: '#ffffff',
            fontSize: 13,
            fontWeight: 400,
          },
          icon: 'square',
          itemWidth: 10,
          itemHeight: 10,
          itemStyle: {
            borderRadius: [5, 5, 5, 5],
          },
          formatter: formatLegendText,
        },
        backgroundColor: 'transparent',
        grid: {
          left: "0%",
          right: "0%",
          bottom: '4%',
          top: "23%",
          containLabel: true,
        },
        xAxis: {
          type: 'category',
          data: barChartData?.categories,
          axisTick: {
            show: false, // Remove the tick marks from the x-axis
          },
          axisLabel: {
            color: '#6A6E76', // Set x-axis label color to white for better visibility
            fontSize: 12,
            formatter: (value: any) => {
              const maxLength = 7;
              return value.length > maxLength ? value.substring(0, maxLength) + '...' : value;
            }
          },
        },
        yAxis: {
          splitLine: {
            lineStyle: {
              type: 'solid',
              color: '#171717', // Set y-axis split line color to grey
            },
          },
          offset: 0,
          axisLine: {
            lineStyle: {
              color: '#6A6E76', // Set y-axis line color to white for better visibility
              fontSize: 8,
            },
          },
        },
        tooltip: {
          // alwaysShowContent: true,
          appendToBody: true,
          trigger: 'item',
          backgroundColor: 'rgba(0,0,0,.75)',
          borderColor: '#1F1F1F',
          borderWidth: 1,
          textStyle: {
            color: '#EEEEEE',
            fontSize: 12,
            fontWeight: 400
          },
          extraCssText: `
    backdrop-filter: blur(10px);
    border-radius: 4px;
    z-index: 9999;
  `,
          formatter: (params: any) => {
            return `
              <div style="text-align: left;text-transform: capitalize echarts-tooltip">
                ${params.name}<br/>
                ${params.value.toFixed(2)}<br/>
              </div>`;
          },
        },
        series: [
          {
            data: barChartData?.data?.map((value: any, index: any) => ({
              value,
              itemStyle: {
                borderRadius: [5, 5, 0, 0], // Top-left and top-right corners rounded
                color: index % 2 === 0 ? barChartData.barColor : barChartData.barColor,
              },
            })),
            type: 'bar',
            barWidth: 22, // Set the width of the bars
            barGap: '0%', // Set the space between bars to 0
          },
        ],
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
  }, [barChartData]);

  return (
    <Box className='relative h-full'>
      {/* <Text_12_500_FFFFFF className='block absolute top-[1.8em] left-[5em]'>{barChartData?.title}</Text_12_500_FFFFFF> */}
      {/* <Text className='block absolute -rotate-90 origin-top-left	 top-[50%] left-[.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{barChartData?.label1}</Text> */}
      <div ref={chartRef} style={{ width: '100%', height: '100%' }} className='' />
      {/* <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{barChartData?.label2}</Text> */}
    </Box>
  );
};

export default BarChart;
