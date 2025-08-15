import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface MultiSeriesLineChartProps {
  data: {
    categories: string[];
    series: {
      name: string;
      data: number[];
      color?: string;
    }[];
    label1?: string;
    label2?: string;
  };
}

const MultiSeriesLineChart: React.FC<MultiSeriesLineChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;

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
          fontSize: 10,
          rotate: 45,
          interval: Math.floor(data.categories.length / 8) // Show ~8 labels
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
        type: 'line',
        data: serie.data,
        smooth: true,
        lineStyle: {
          width: 2,
          color: serie.color || colors[index % colors.length]
        },
        itemStyle: {
          color: serie.color || colors[index % colors.length]
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: `${serie.color || colors[index % colors.length]}33`
            },
            {
              offset: 1,
              color: `${serie.color || colors[index % colors.length]}08`
            }
          ])
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

  return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />;
};

export default MultiSeriesLineChart;
