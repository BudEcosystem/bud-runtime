import React, { useState, useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { Box, Text } from '@radix-ui/themes';

export enum Entity {
    Model = 'model',
    Project = 'project',
    Endpoint = 'endpoint'
}

interface GaugeChartProps {
    props: {
        title: string,
        value: number,
        color: string,
        proportion?: number
    };
}

const GaugeChart: React.FC<GaugeChartProps> = ({ props }) => {
    const chartRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (chartRef.current) {
            const containerWidth = chartRef.current.clientWidth;
            const containerHeight = chartRef.current.clientHeight;

            if (containerWidth === 0 || containerHeight === 0) {
                console.warn("guage Chart container has no width or height yet.");
                return;
            }
            const myChart = echarts.init(chartRef.current, null, {
                renderer: 'canvas',
                useDirtyRect: false,
            });
            const option = {
                backgroundColor: 'transparent',
                series: [
                    {
                        center: ["50%", "40%"],
                        type: 'gauge',
                        startAngle: 0,
                        endAngle: -360,
                        radius: props?.proportion > 0 ? props.proportion * 25 : 25,
                        pointer: {
                            show: false
                        },
                        progress: {
                            show: true,
                            overlap: false,
                            roundCap: false,
                            clip: false,
                            itemStyle: {
                                color: props?.color
                            }
                        },
                        axisLine: {
                            lineStyle: {
                                width: props?.proportion > 0 ? props.proportion * 2 : 2,
                                color: [[1, props?.color]],
                                opacity: 0.2
                            }
                        },
                        splitLine: {
                            show: false,
                            distance: 0,
                            length: 10
                        },
                        axisTick: {
                            show: false
                        },
                        axisLabel: {
                            show: false,
                            distance: 20
                        },
                        data: [
                            {
                                value: props?.value.toFixed(0),
                                name: props?.title,
                                title: {
                                    offsetCenter: ['0%', '160%'],
                                    fontSize: props?.proportion > 0 ? props.proportion * 12 : 12,
                                    fontWeight: '100',
                                    color: '#FFFFFF',
                                },
                                detail: {
                                    valueAnimation: true,
                                    offsetCenter: ['0%', '10%']
                                }
                            }
                        ],
                        title: {
                            fontSize: props?.proportion > 0 ? props.proportion * 12 : 12,
                            offsetCenter: ['0%', '10%']
                        },
                        detail: {
                            animation: true,
                            width: 50,
                            height: 14,
                            fontSize: props?.proportion > 0 ? props.proportion * 12 : 12,
                            fontFamily: 'sans-serif',
                            fontWeight: '100',
                            color: '#FFFFFF',
                            formatter: '{value}%'
                        }
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
    }, [props]);


    return (
        <Box ref={chartRef} width="200px" height="108px" className='relative w-auto h-full bg-neutral-900 rounded-md align-baseline cursor-pointer' />
    );
}

export default GaugeChart;
