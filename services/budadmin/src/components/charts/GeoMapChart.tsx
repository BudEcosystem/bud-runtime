import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { Text_12_400_B3B3B3 } from '@/components/ui/text';

interface GeoMapChartProps {
  data?: {
    country: string;
    value: number;
    lat?: number;
    lng?: number;
  }[];
}

const GeoMapChart: React.FC<GeoMapChartProps> = ({ data = [] }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    const chart = echarts.init(chartRef.current, 'dark');

    // Sample data for demonstration - replace with actual data when available
    const sampleData = data.length > 0 ? data : [
      { name: 'United States', value: 450, coords: [-95.7129, 37.0902] },
      { name: 'United Kingdom', value: 280, coords: [-3.4360, 55.3781] },
      { name: 'Germany', value: 220, coords: [10.4515, 51.1657] },
      { name: 'Japan', value: 180, coords: [138.2529, 36.2048] },
      { name: 'Canada', value: 150, coords: [-106.3468, 56.1304] },
      { name: 'France', value: 140, coords: [2.2137, 46.2276] },
      { name: 'Australia', value: 120, coords: [133.7751, -25.2744] },
      { name: 'India', value: 110, coords: [78.9629, 20.5937] },
      { name: 'Brazil', value: 95, coords: [-51.9253, -14.2350] },
      { name: 'Singapore', value: 85, coords: [103.8198, 1.3521] },
    ];

    const maxValue = Math.max(...sampleData.map(d => d.value));

    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: function(params: any) {
          if (params.value) {
            return `${params.name}<br/>Requests: ${params.value[2]}`;
          }
          return params.name;
        },
        backgroundColor: '#1a1a1a',
        borderColor: '#333',
        textStyle: {
          color: '#EEEEEE',
          fontSize: 12
        }
      },
      geo: {
        map: 'world',
        roam: true,
        zoom: 1.2,
        itemStyle: {
          areaColor: '#1a1a1a',
          borderColor: '#333',
          borderWidth: 0.5
        },
        emphasis: {
          itemStyle: {
            areaColor: '#2a2a2a',
            borderColor: '#666',
            borderWidth: 1
          }
        },
        regions: sampleData.map(item => ({
          name: item.name,
          itemStyle: {
            areaColor: '#2a3f5f',
            borderColor: '#3F8EF7',
            borderWidth: 1
          },
          emphasis: {
            itemStyle: {
              areaColor: '#3F8EF7',
              borderColor: '#5FA5F7',
              borderWidth: 2
            }
          }
        }))
      },
      series: [
        {
          type: 'scatter',
          coordinateSystem: 'geo',
          data: sampleData.map(item => ({
            name: item.name,
            value: [...item.coords, item.value]
          })),
          symbolSize: function(val: number[]) {
            return Math.max(10, (val[2] / maxValue) * 40);
          },
          itemStyle: {
            color: '#FFC442',
            borderColor: '#FFDD88',
            borderWidth: 1,
            shadowBlur: 10,
            shadowColor: 'rgba(255, 196, 66, 0.3)'
          },
          emphasis: {
            itemStyle: {
              borderColor: '#FFFFFF',
              borderWidth: 2,
              shadowBlur: 15,
              shadowColor: 'rgba(255, 196, 66, 0.5)'
            }
          }
        }
      ]
    };

    // Register world map if not already registered
    fetch('https://cdn.jsdelivr.net/npm/echarts@5/map/json/world.json')
      .then(response => response.json())
      .then(worldJson => {
        echarts.registerMap('world', worldJson);
        chart.setOption(option);
      })
      .catch(error => {
        console.error('Failed to load world map:', error);
        // Fallback to simple visualization without map
        const fallbackOption: echarts.EChartsOption = {
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'axis',
            backgroundColor: '#1a1a1a',
            borderColor: '#333',
            textStyle: {
              color: '#EEEEEE'
            }
          },
          xAxis: {
            type: 'category',
            data: sampleData.map(d => d.name),
            axisLabel: {
              color: '#B3B3B3',
              rotate: 45,
              interval: 0
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
              color: '#B3B3B3'
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
          series: [{
            data: sampleData.map(d => d.value),
            type: 'bar',
            itemStyle: {
              color: '#3F8EF7'
            }
          }]
        };
        chart.setOption(fallbackOption);
      });

    const handleResize = () => {
      chart.resize();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.dispose();
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[20rem]">
        <Text_12_400_B3B3B3>Geographic data will be available when gateway metadata is enabled</Text_12_400_B3B3B3>
      </div>
    );
  }

  return <div ref={chartRef} style={{ width: '100%', height: '20rem' }} />;
};

export default GeoMapChart;
