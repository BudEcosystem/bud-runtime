import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface GroupedBarChartProps {
  data: {
    categories: string[];
    series: {
      name: string;
      data: number[];
      color?: string;
    }[];
  };
}

const GroupedBarChart: React.FC<GroupedBarChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  // Check if data is empty
  const hasData = data?.series && data.series.length > 0 &&
                  data.series.some(s => s.data && s.data.length > 0 && s.data.some(val => val > 0));

  useEffect(() => {
    if (!chartRef.current || !hasData) return;

    const chart = echarts.init(chartRef.current, 'dark');

    // Color palette for different series
    const colors = [
      '#3F8EF7', '#965CDE', '#FFC442', '#52C41A', '#FF6B6B',
      '#4ECDC4', '#A8E6CF', '#FFD93D', '#FF8CC6', '#95E1D3'
    ];

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        },
        backgroundColor: '#1a1a1a',
        borderColor: '#333',
        textStyle: {
          color: '#EEEEEE',
          fontSize: 12
        }
      },
      legend: {
        data: data.series.map(s => s.name),
        textStyle: {
          color: '#B3B3B3',
          fontSize: 11
        },
        bottom: 0,
        left: 'center',
        orient: 'horizontal',
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 15
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '5%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: data.categories,
        axisLabel: {
          color: '#B3B3B3',
          fontSize: 10
        },
        axisLine: {
          lineStyle: {
            color: '#333'
          }
        }
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#B3B3B3',
          fontSize: 10
        },
        splitLine: {
          lineStyle: {
            color: '#1F1F1F'
          }
        },
        axisLine: {
          lineStyle: {
            color: '#333'
          }
        }
      },
      series: data.series.map((serie, index) => ({
        name: serie.name,
        type: 'bar',
        data: serie.data,
        itemStyle: {
          color: serie.color || colors[index % colors.length],
          borderRadius: [2, 2, 0, 0]
        },
        emphasis: {
          itemStyle: {
            color: serie.color || colors[index % colors.length]
          }
        }
      }))
    };

    chart.setOption(option);

    const handleResize = () => {
      chart.resize();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.dispose();
    };
  }, [data]);

  // Show no data message
  if (!hasData) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-[#757575] text-sm">No data available</p>
        </div>
      </div>
    );
  }

  return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />;
};

export default GroupedBarChart;
