import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { Box } from '@radix-ui/themes';
import { getChromeColorHex } from '@/components/ui/bud/dataEntry/TagsInputData';
import { Text_15_400_EEEEEE, Text_18_400_EEEEEE, Text_18_500_EEEEEE, Text_20_400_EEEEEE, Text_26_400_EEEEEE } from '@/components/ui/text';
import { Image } from 'antd';

interface AccuracyPopupProps {
  data: {
    dimensions: string[];
    source: Array<{ [key: string]: number | string }>;
  };
  extraChartDetails: any;
}

interface CustomLegendProps {
  onToggleSeries: (seriesName: string) => void;
  extraChartDetails: any;
  legendSelection: { [key: string]: boolean };
}

const CustomLegend: React.FC<CustomLegendProps> = ({ onToggleSeries, extraChartDetails, legendSelection }) => {
  return (
    <div>
      <div className="flex flex-col justify-center items-start mt-[1.45rem] gap-[.3rem] mt-[1.5rem]">

        <div className='flex items-center justify-center'>
          <div
            onClick={() => onToggleSeries('Input Tokens')}
            style={{ cursor: 'pointer' }}
            className='flex justify-start items-center gap-[.5rem] w-[8.8rem]'
          >
            <div
              style={{
                width: '.68rem',
                height: '.68rem',
                backgroundColor: legendSelection['Input Tokens'] ? '#D1B854' : 'white',
                borderRadius: '2px'
              }}
            />
            <Text_15_400_EEEEEE>Input Tokens</Text_15_400_EEEEEE>
          </div>

          <div
            className="flex justify-between items-center gap-[.5rem]  pt-[.3rem] pb-[.3rem] px-[.6rem] rounded-md"
            style={{

            }}
          >
            <Text_18_400_EEEEEE className='min-w-[70px]'>
              {Number(Math.abs(extraChartDetails.token_metrics.total_input_value)).toFixed(2)}
            </Text_18_400_EEEEEE>
            <div className={`flex ${Number(extraChartDetails.token_metrics.input_avg) >= 0 ? 'text-[#479D5F] bg-[#122F1140]' : 'bg-[#861A1A33] text-[#EC7575]'} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.2rem]`}>
              <span className="font-[400] text-[0.8125rem] leading-[100%]">
                Avg. {Number(Math.abs(extraChartDetails.token_metrics.input_avg)).toFixed(2)}%
              </span>
              {Number(extraChartDetails.token_metrics.input_avg) >= 0 ? (
                <Image preview={false} width={12} src="/images/dashboard/greenArrow.png" className="ml-[.2rem]" alt="" />
              ) : (
                <Image preview={false} width={12} src="/images/dashboard/redArrow.png" className="ml-[.2rem]" alt="" />
              )}
            </div>
          </div>
        </div>

        <div className='flex items-center justify-center'>
          <div
            onClick={() => onToggleSeries('Output Tokens')}
            style={{ cursor: 'pointer' }}
            className='flex justify-start items-center gap-[.5rem]  w-[8.8rem]'
          >
            <div
              style={{
                width: '.68rem',
                height: '.68rem',
                backgroundColor: legendSelection['Output Tokens'] ? '#479D5F' : 'white',
                borderRadius: '2px'
              }}
            />
            <Text_15_400_EEEEEE>Output Tokens</Text_15_400_EEEEEE>
          </div>

          <div
            className="flex justify-between items-center gap-[.5rem] pt-[.3rem] pb-[.3rem] px-[.6rem] rounded-md"
            style={{

            }}
          >
            <Text_18_400_EEEEEE className='min-w-[70px]'>
              {Number(Math.abs(extraChartDetails.token_metrics.total_output_value)).toFixed(2)}
            </Text_18_400_EEEEEE>
            <div className={`flex ${Number(extraChartDetails.token_metrics.output_avg) >= 0 ? 'text-[#479D5F] bg-[#122F1140]' : 'bg-[#861A1A33] text-[#EC7575]'} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.2rem]`}>
              <span className="font-[400] text-[0.8125rem] leading-[100%]">
                Avg. {Number(Math.abs(extraChartDetails.token_metrics.output_avg)).toFixed(2)}%
              </span>
              {Number(extraChartDetails.token_metrics.output_avg) >= 0 ? (
                <Image preview={false} width={12} src="/images/dashboard/greenArrow.png" className="ml-[.2rem]" alt="" />
              ) : (
                <Image preview={false} width={12} src="/images/dashboard/redArrow.png" className="ml-[.2rem]" alt="" />
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

interface TokenMetricsChartProps {
  data: {
    dimensions: string[];
    source: Array<{ [key: string]: number | string }>;
  };
  extraChartDetails: any;
}

const TokenMetricsChart: React.FC<TokenMetricsChartProps> = ({ data, extraChartDetails }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<any>(null);
  const [barChartData, setBarChartData] = useState<any>(data);
  const [legendSelection, setLegendSelection] = useState({
    'Input Tokens': true,
    'Output Tokens': true,
  });

  useEffect(() => {
    if (data) {
      setBarChartData(data);
    }
  }, [data]);

  useEffect(() => {
    console.log('legendSelection', legendSelection)
    console.log('legendSelection', legendSelection['Input Tokens'])
    console.log('legendSelection', legendSelection['Output Tokens'])
  }, [legendSelection]);

  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;
      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("Token metrics Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: 'canvas',
        useDirtyRect: false,
      });
      chartInstanceRef.current = myChart;

      const option = {
        backgroundColor: 'transparent',
        // Disable built-in legend (we're using our custom legend)
        legend: { show: false },
        grid: {
          right: '0%',
          left: '0%',
          top: '16.5%',
          bottom: '20%',
          containLabel: true,
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(44, 44, 44, .6)',
          borderWidth: 0,
          textStyle: {
            color: '#ffffff',
            fontSize: 12,
          },
          padding: 0,
          extraCssText: `backdrop-filter: blur(4.2px);border-radius:4px;`,
          formatter: (params: any) => {
            if (!legendSelection['Input Tokens'] && !legendSelection['Output Tokens']) {
              return ''; // Hide tooltip
            }
            const seriesData = params.map(
              (item: any) =>
                `<div style="margin-bottom: 7px;">
                   <span style="display:inline-block;width:10px;height:10px;background-color:${item.color};margin-right:15px;border-radius:2px;font-size:13px;"></span>
                   <span style="margin-right: 15px;display:inline-block;min-width:50px;">${item.value[item.seriesName]}</span>
                   ${item.seriesName}
                 </div>`
            );
            return `<div style="text-align:left; padding: 20px;position:relative;overflow:hidden;">
                      <img style="position:absolute;bottom:0;right:0;z-index:0;" src="/images/tooltip-pattern.svg"></img>
                      <div style="font-weight:bold;margin-bottom:10px;font-size:15px;font-weight:600;padding:0 10px;">
                      <img style="display:inline-block;height:20px;width:20px;margin-right:5px;" src="/images/drawer/cloud.png"></img>
                      ${params[0].axisValue}</div>
                      <div style="background-color: #161616;padding: 10px;border-radius:6px;position:relative;z-index:1;">${seriesData.join('')}</div>
                    </div>`;
          },
          axisPointer: {
            type: 'none',
          },
        },
        dataset: {
          dimensions: barChartData.dimensions,
          source: barChartData.source,
        },
        xAxis: {
          type: 'category',
          axisLine: { lineStyle: { color: '#2d2d2d' } },
          axisLabel: {
            color: '#6A6E76',
            fontSize: 12,
            formatter: (value: string) => {
              const maxLength = 5;
              return value.length > maxLength ? value.slice(0, maxLength) + '...' : value;
            },
          },
          axisTick: { show: false },
        },
        yAxis: {
          minInterval: 40,
          splitNumber: 6,
          splitLine: { lineStyle: { type: 'solid', color: '#171717' } },
          axisLine: { lineStyle: { color: '#2d2d2d' } },
          axisLabel: {
            color: '#6A6E76',
            fontSize: 12,
            formatter: function (value: number) {
              const abs = Math.abs(value);
              if (abs >= 1_000_000_000) {
                const scaled = value / 1_000_000_000;
                return (scaled >= 100 ? scaled.toFixed(0) : scaled.toFixed(1)) + 'B';
              }
              if (abs >= 1_000_000) {
                const scaled = value / 1_000_000;
                return (scaled >= 100 ? scaled.toFixed(0) : scaled.toFixed(1)) + 'M';
              }
              if (abs >= 1_000) {
                const scaled = value / 1_000;
                return (scaled >= 100 ? scaled.toFixed(0) : scaled.toFixed(1)) + 'K';
              }
              return value.toString();
            }
          },
        },
        series: [
          {
            type: 'bar',
            barWidth: 8,
            barGap: '0%',
            itemStyle: {
              color: '#D1B854',
              borderRadius: [5, 5, 0, 0],
            },
            emphasis: {
              itemStyle: {
                opacity: 1, // Ensures the bar stays fully visible on hover
              },
            },
          },
          {
            type: 'bar',
            barWidth: 8,
            barGap: '0%',
            itemStyle: {
              color: '#479D5F',
              borderRadius: [5, 5, 0, 0],
            },
            emphasis: {
              itemStyle: {
                opacity: 1,
              },
            },
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
  }, [barChartData, legendSelection]);

  // Handler to toggle series visibility and update legend selection state
  const handleToggleSeries = (seriesName: string) => {
    const newSelection = {
      ...legendSelection,
      // need to check the params  uncomment next line
      // [seriesName]: !legendSelection[seriesName],
    };
    setLegendSelection(newSelection);
    if (!newSelection['Input Tokens'] && !newSelection['Output Tokens']) {
      chartInstanceRef.current.setOption({ yAxis: { show: false } });
    } else {
      chartInstanceRef.current.setOption({ yAxis: { show: true } });
    }
    if (chartInstanceRef.current) {
      const option = chartInstanceRef.current.getOption();
      console.log('option', option)
      const series = option.series.map((s: any, index: number) => {
        const seriesName = index === 0 ? 'Input Tokens' : 'Output Tokens';
        return {
          ...s,
          itemStyle: {
            ...s.itemStyle,
            opacity: newSelection[seriesName] ? 1 : 0,
          },
          emphasis: {
            itemStyle: {
              opacity: newSelection[seriesName] ? 1 : 0
            }
          },
          tooltip: {
            show: newSelection[seriesName] ? true : false,
          }
        };
      });
      chartInstanceRef.current.setOption({ series });
    }
  };

  return (
    <Box className="relative h-full">
      <CustomLegend
        onToggleSeries={handleToggleSeries}
        extraChartDetails={extraChartDetails}
        legendSelection={legendSelection}
      />
      <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
    </Box>
  );
};

export default TokenMetricsChart;
