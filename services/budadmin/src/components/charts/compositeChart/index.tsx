import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface ChartProps {
  data: {
    data: string[];
    categories: string[];
  };
}

const CompositeChart = ({data}: ChartProps) => {
  const chartRef = useRef(null);

  useEffect(() => {
    const chart = echarts.init(chartRef.current);

    const xData = data.categories;

    const yData = data.data;
    const START_COUNT = 10; 
    const END_COUNT = 10;
    const total = yData.length;

    const option = {
      grid: {
        top: 30,
        bottom: 30,
        left: 40,
        right: 20
      },
      graphic: {
            type: "rect",
            left: 0,
            top: 0,
            shape: { width: "100%", height: "100%" },
            style: {
            fill: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "#1c1027" },
                { offset: 1, color: "#0c0712" }
            ])
            }
        },

      xAxis: {
        type: "category",
        data: xData,
        axisLine: { lineStyle: { color: "#888" } },
        axisLabel: {
            color: "#ccc",
            interval: 3
        }
      },

      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: "#888" } },
        axisLabel: { color: "#bbb" },
        splitLine: { lineStyle: { color: "#333" } }
      },

      series: [
        {
          name: "Bar",
          type: "bar",
          data: yData.map((v, i) => {
            const isVisible = i < START_COUNT || i >= total - END_COUNT;
            return isVisible ? v : null;   // ⬅️ removes bar + spacing
          }),
          barWidth:  yData.length > 10 ? yData.length % 10 : 7,
          itemStyle: {
            borderRadius: [5, 5, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#b88be3ff" },
              { offset: 1, color: "#723ec1ff" }
            ])
          }
        },
        {
          name: "Line",
          type: "line",
          data: yData,
          smooth: false,
          symbol: "",
          symbolSize: 0,
          lineStyle: { color: "#f3dd4a", width: 2 },
          itemStyle: { color: "#f3dd4a" }
        }
      ]
    };

    chart.setOption(option);

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [data]);

  return (
    <div
      ref={chartRef}
      style={{ width: "100%", height: "100%" }}
    />
  );
};

export default CompositeChart;
