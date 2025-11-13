import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

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
    yAxisUnit?: string; // Unit to display on Y-axis (e.g., "%", "Mbps", "GB")
    yAxisAutoScale?: boolean; // If true, auto-scale Y-axis based on data
    yAxisMin?: number; // Minimum Y-axis value (ignored if yAxisAutoScale is true)
    yAxisMax?: number; // Maximum Y-axis value (ignored if yAxisAutoScale is true)
    yAxisInterval?: number; // Y-axis interval (ignored if yAxisAutoScale is true)
  };
}

const MultiSeriesLineChart: React.FC<MultiSeriesLineChartProps> = ({
  data,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !data) return;

    const chart = echarts.init(chartRef.current, "dark");

    // Color palette for different series
    const colors = [
      "#3F8EF7",
      "#965CDE",
      "#FFC442",
      "#52C41A",
      "#FF6B6B",
      "#4ECDC4",
      "#A8E6CF",
      "#FFD93D",
      "#FF8CC6",
      "#95E1D3",
    ];

    // Calculate Y-axis range if auto-scale is enabled
    let yAxisMin = data.yAxisMin ?? undefined;
    let yAxisMax = data.yAxisMax ?? undefined;
    let yAxisInterval = data.yAxisInterval ?? undefined;

    if (data.yAxisAutoScale && data.series && data.series.length > 0) {
      // Collect all data values from all series
      const allValues = data.series.flatMap((serie) => serie.data || []);

      if (allValues.length > 0) {
        const minValue = Math.min(...allValues);
        const maxValue = Math.max(...allValues);

        // Add 10% padding to top and bottom for better visualization
        const range = maxValue - minValue;
        const padding = range * 0.1;
        yAxisMin = Math.max(0, Math.floor(minValue - padding));
        yAxisMax = Math.ceil(maxValue + padding);

        // Calculate a nice interval (roughly 4-5 ticks)
        const roughInterval = (yAxisMax - yAxisMin) / 4;
        // Round to nearest "nice" number (1, 2, 5, 10, 20, 50, etc.)
        const magnitude = Math.pow(10, Math.floor(Math.log10(roughInterval)));
        const normalizedInterval = roughInterval / magnitude;
        if (normalizedInterval <= 1) yAxisInterval = magnitude;
        else if (normalizedInterval <= 2) yAxisInterval = 2 * magnitude;
        else if (normalizedInterval <= 5) yAxisInterval = 5 * magnitude;
        else yAxisInterval = 10 * magnitude;
      }
    }

    const yAxisUnit = data.yAxisUnit ?? "";

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1a1a1a",
        borderColor: "#333",
        textStyle: {
          color: "#EEEEEE",
          fontSize: 12,
        },
      },
      legend: {
        data: data.series.map((s) => s.name),
        textStyle: {
          color: "#B3B3B3",
          fontSize: 11,
        },
        bottom: 0,
        left: "center",
        orient: "horizontal",
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 15,
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "15%",
        top: "5%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: data.categories || [],
        axisLabel: {
          color: "#B3B3B3",
          fontSize: 10,
          rotate: 45,
          interval: Math.floor((data.categories?.length || 0) / 8), // Show ~8 labels
        },
        axisLine: {
          lineStyle: {
            color: "#333",
          },
        },
      },
      yAxis: {
        type: "value",
        min: yAxisMin,
        max: yAxisMax,
        interval: yAxisInterval,
        axisLabel: {
          color: "#B3B3B3",
          fontSize: 10,
          formatter: (value: number) => `${value}${yAxisUnit}`,
        },
        splitLine: {
          lineStyle: {
            color: "#1F1F1F",
          },
        },
        axisLine: {
          lineStyle: {
            color: "#333",
          },
        },
      },
      series: (data.series || []).map((serie, index) => ({
        name: serie.name,
        type: "line",
        data: serie.data,
        smooth: true,
        lineStyle: {
          width: 2,
          color: serie.color || colors[index % colors.length],
        },
        itemStyle: {
          color: serie.color || colors[index % colors.length],
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: `${serie.color || colors[index % colors.length]}33`,
            },
            {
              offset: 1,
              color: `${serie.color || colors[index % colors.length]}08`,
            },
          ]),
        },
      })),
    };

    chart.setOption(option);

    const handleResize = () => {
      chart.resize();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [data]);

  return <div ref={chartRef} style={{ width: "100%", height: "100%" }} />;
};

export default MultiSeriesLineChart;
