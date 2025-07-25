import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
interface DirectionArrowChartProps {
  categories?: string[];
  data?: number[];
  classNames?: string;
  chartAdjust?: {
    [key: string]: any; // For additional customization
  };
}
const DirectionArrowChart: React.FC<DirectionArrowChartProps> = ({
  categories,
  data,
  classNames,
  chartAdjust = {},
}) => {
  const chartRef = useRef(null);
  useEffect(() => {
    const chartInstance = echarts.init(chartRef.current);

    // Calculate the last data point and arrow direction
    const lastIndex = data?.length - 1;
    const lastValue = data[lastIndex];
    const secondLastValue = data[lastIndex - 1] || lastValue;
    const arrowRotation = lastValue === secondLastValue ? -90 : lastValue > secondLastValue ? -30 : 205;

    const option = {
      backgroundColor: 'transparent',
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
      grid: {
        bottom: chartAdjust.bottom ?  chartAdjust.bottom : '0%',
        top: chartAdjust.top ?  chartAdjust.top : '50%',
        left: 3,
        right: 3
      },
      series: [
        {
          data, 
          type: 'line',
          lineStyle: {
            color: '#9462D5',
            width: 1.5,
          },
          symbol: 'none',
          markPoint: {
            data: [
              {
                coord: [lastIndex, lastValue], 
              },
            ],
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(148, 98, 213, 0.28)' }, // Top color
              { offset: 0.5, color: 'rgba(148, 98, 213, 0.1)' }, // Middle color
              { offset: 1, color: 'rgba(148, 98, 213, 0)' },     // Bottom color
            ]),
          },
        },
      ],
    };

    chartInstance.setOption(option);
    const getCoordinatesAndAngle = () => {
        const lastIndex = data.length - 1;
        const secondLastIndex = data.length - 2;
        const lastCoord = chartInstance.convertToPixel('grid', [categories[lastIndex], data[lastIndex]]);
        const secondLastCoord = chartInstance.convertToPixel('grid', [categories[secondLastIndex], data[secondLastIndex]]);
        
        const deltaX = lastCoord[0] - secondLastCoord[0]; // x2 - x1
        const deltaY = lastCoord[1] - secondLastCoord[1]; // y2 - y1

        const angleInRadians = Math.atan2(deltaY, deltaX);

        // Convert radians to degrees
        const angleInDegrees = angleInRadians * (180 / Math.PI);

        return angleInDegrees;
    };
  
    const angleInDegrees = getCoordinatesAndAngle();

    // Update the chart with the new angle
    chartInstance.setOption({
      series: [
        {
          markPoint: {
            data: [
              {
                coord: [data.length - 1, data[data.length - 1]],
                symbol: 'arrow',
                symbolSize: 7,
                symbolRotate: 270 - angleInDegrees, // Set the calculated angle for symbol rotation
                itemStyle: { color: '#9462D5' },
              },
            ],
          },
        },
      ],
    });

    // Clean up on unmount
    return () => {
      chartInstance.dispose();
    };
  }, [categories, data]); // Re-run when categories or data change

  return <div ref={chartRef}  style={{ width: '100%', height: '100%' }}  className={`${classNames}`}/>;
};

export default DirectionArrowChart;
