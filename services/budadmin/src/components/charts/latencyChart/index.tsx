import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { Box, Text } from '@radix-ui/themes';

interface LatencyChartProps {
  data: {
    categories: string[];
    series: any;
  };
  Legend?: boolean
}

const LatencyChart: React.FC<LatencyChartProps> = ({ data, Legend }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const formatLegendText = (text: string) => {
    // Replace special characters with a space and capitalize the first letter of each word
    return text
      .replace(/[^a-zA-Z0-9]/g, ' ')
      .replace(/\b\w/g, char => char.toUpperCase());
  };
  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("latency Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: 'canvas',
        useDirtyRect: false,
      });

      const customLabels = [0, 200, 400, 600, 800];

      const option = {
        backgroundColor: 'transparent',
        
        legend: {
          show: Legend, 
          orient: 'horizontal', // Arrange legend items vertically
          left: '0%', // Position the legend on the right side
          top: 'top', // Vertically center the legend
          textStyle: {
            color: '#ffffff', // Set legend text color to white for better visibility
            fontSize: 13,
            fontWeight: 400
          },
          icon: 'square', // Set legend item shape to round
          itemWidth: 10, // Adjust the width of the legend icon
          itemHeight: 10,
          itemStyle: {
            borderRadius: [5, 5, 5, 5]
          },
          data: data.series.map((item) => ({
            name: item.name,
            icon: 'rect', // Set custom icon
            itemStyle: {
              color: item.lineColor, // Set legend icon color to match line color
            },
          })),
          formatter: formatLegendText,
        },
        grid: {
          right: '0%', // Adjust this value to create more space for the legend
          left: '6.5%'
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: data.categories,
          axisTick: {
            show: false, // Remove the tick marks from the x-axis
          },
          axisLabel: {
            color: '#6A6E76', // Set x-axis label color to white for better visibility
            fontSize: 12,
          },
          splitLine: {
            show: false,
          },
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 650,
          interval: 50, // Adjust interval to ensure all custom labels are displayed
          axisLabel: {
            formatter: (value: number) => (customLabels.includes(value) ? value.toString() : ''),
            color: '#6A6E76',
            fontSize: 12,
          },
          splitLine: {
            lineStyle: {
              type: 'solid',
              color: '#171717', // Set y-axis split line color to grey
            },
          },
        },
        series: data.series.map((item) => ({
          name: item.name,
          data: item.data,
          type: 'line',
          smooth: true,
          areaStyle: {},
          opacity: 0.8,
          lineStyle: {
            color: item.lineColor, // Line color
          },
          color: new echarts.graphic.LinearGradient(0.75, 0, 0, 1, item.color),
          symbol: 'none', // Remove the dots in the data lines
        })),
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
  }, [data]);

  return (
    <Box className='relative h-full'>
      {/* <Text className='block absolute -rotate-90 origin-top-left top-[50%] left-[0.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>
        Latency
      </Text> */}
      <div ref={chartRef} style={{ width: '100%', height: '100%' }} className='' />
      {/* <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>
        Tasks
      </Text> */}
    </Box>
  );
};

export default LatencyChart;
