import React, { useState, useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { Box, Text } from '@radix-ui/themes';
import { AppRequest } from "src/pages/api/requests";
import { Text_12_500_FFFFFF } from '@/components/ui/text';

interface LineChartProps {
    data: {
        categories: string[];
        data: number[];
        label1?: string;
        label2?: string;
        color?: string;
        smooth?: boolean;
    };
}

const LineChartCustom: React.FC<LineChartProps> = ({ data }) => {
    const [lineChartData, setLineChartData] = useState<any>(data);

    useEffect(() => {
        if (data) {
            setLineChartData(data);
        }
    }, [data]);

    const chartRef = useRef<HTMLDivElement>(null);
    // const [lineChartProps, setLineChartProps] = useState(data);

    useEffect(() => {
        if (chartRef.current) {
            const containerWidth = chartRef.current.clientWidth;
            const containerHeight = chartRef.current.clientHeight;

            if (containerWidth === 0 || containerHeight === 0) {
                console.warn("line Chart container has no width or height yet.");
                return;
            }
            const myChart = echarts.init(chartRef.current, null, {
                renderer: 'canvas',
                useDirtyRect: false,
            });

            const option = {
                backgroundColor: 'transparent',
                grid: {
                    left: "10%"
                },
                xAxis: {
                    type: 'category',
                    data: lineChartData?.categories,
                    axisTick: {
                        show: false, // Remove the tick marks from the x-axis
                    },
                    axisLabel: {
                        color: '#6A6E76', // Set x-axis label color to white for better visibility
                        fontSize: 10,
                    },
                },
                yAxis: {
                    splitLine: {
                        lineStyle: {
                            type: 'solid',
                            color: '#212225', // Set y-axis split line color to grey
                        },
                    },
                    offset: 0,
                    axisLine: {
                        lineStyle: {
                            color: '#6A6E76', // Set y-axis line color to white for better visibility
                            fontSize: 10,
                        },
                    },
                },
                series: [
                    {
                        color: lineChartData?.color,
                        data: lineChartData?.data?.map((value, index) => ({
                            value,
                            itemStyle: {
                                borderRadius: [5, 5, 0, 0], // Top-left and top-right corners rounded
                                color: index % 2 === 0 ? '#3F8EF7' : '#D45453',
                            },
                        })),
                        type: 'line',
                        lineStyle: {
                            color: lineChartData?.color
                        },
                        smooth: lineChartData?.smooth,
                        showSymbol: false
                    },
                ],
                tooltip: {
                    trigger: 'axis',
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
                        <div style="text-align: left;text-transform: capitalize;padding: 0 5px;">
                            ${params[0].name}<br/>
                            <div>
                            <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${params[0].color}; margin-right: 5px;"></span>
                            ${params[0].value}<br/></div>
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
    }, [lineChartData]);

    return (
        <Box height="200px" className='relative h-full '>
            <Text_12_500_FFFFFF className='block absolute top-[1.8em] left-[5em]'>{lineChartData?.title}</Text_12_500_FFFFFF>
            <Text className='block absolute -rotate-90 origin-top-left	 top-[50%] left-[.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{lineChartData?.label1}</Text>
            <div ref={chartRef} style={{ width: '100%', height: '105%' }} className='pl-[.7rem] borderbox' />
            <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{lineChartData?.label2}</Text>
        </Box>
    );
};
export default LineChartCustom;
