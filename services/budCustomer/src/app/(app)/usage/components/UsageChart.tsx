import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Rectangle,
} from "recharts";
import { motion } from "framer-motion";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import styles from "./UsageChart.module.scss";

dayjs.extend(utc);

interface UsageChartProps {
  data: any[];
  type: "spend" | "tokens" | "requests";
  loading?: boolean;
  timeRange: string;
}

const UsageChart: React.FC<UsageChartProps> = ({
  data,
  type,
  loading = false,
  timeRange,
}) => {
  const chartConfig = useMemo(() => {
    const configs = {
      spend: {
        dataKey: "cost",
        color: "#7c3aed",
        label: "Cost ($)",
        formatter: (value: number) => `$${value.toFixed(2)}`,
      },
      tokens: {
        dataKey: "tokens",
        color: "#3b82f6",
        label: "Tokens",
        formatter: (value: number) => value.toLocaleString(),
      },
      requests: {
        dataKey: "requests",
        color: "#10b981",
        label: "Requests",
        formatter: (value: number) => value.toLocaleString(),
      },
    };
    return configs[type];
  }, [type]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload[0]) {
      // The label contains the original date from the data
      const fullDate = payload[0].payload.date
        ? dayjs(payload[0].payload.date).utc().format("MMM D, YYYY [UTC]")
        : label;

      // Show different content based on whether there's data
      if (payload[0].payload.hasData === false) {
        return (
          <div className={styles.customTooltip}>
            <p className={styles.label}>{fullDate}</p>
            <p className={styles.noDataText}>No usage</p>
          </div>
        );
      }

      return (
        <div className={styles.customTooltip}>
          <p className={styles.label}>{fullDate}</p>
          <p className={styles.value}>
            {chartConfig.formatter(payload[0].value)}
          </p>
        </div>
      );
    }
    return null;
  };

  const maxValue = useMemo(() => {
    if (!data || data.length === 0) return 0;
    return Math.max(...data.map((item) => item[chartConfig.dataKey] || 0));
  }, [data, chartConfig.dataKey]);

  // Custom bar shape with baseline
  const CustomBar = (props: any) => {
    const { fill, x, y, width, height, payload } = props;
    const barWidth = width * 0.8; // 80% of allocated width for bar
    const barX = x + (width - barWidth) / 2; // Center the bar
    const baselineY = y + height; // Bottom position

    // Check if light theme
    const isLightTheme = document.documentElement.getAttribute('data-theme') === 'light';
    const baselineColor = isLightTheme ? '#d1d5db' : '#4a4a4a';

    return (
      <g>
        {/* Baseline segment with gap */}
        <rect
          x={x + width * 0.05}
          y={baselineY}
          width={width * 0.9}
          height={1.5}
          fill={baselineColor}
          opacity={1}
        />
        {/* Bar */}
        {payload.hasData !== false && height > 0 && (
          <rect
            x={barX}
            y={y}
            width={barWidth}
            height={height}
            fill={fill}
            rx={3}
            ry={3}
          />
        )}
      </g>
    );
  };

  if (loading) {
    return (
      <div className={styles.chartContainer}>
        <div className={styles.loadingState}>
          <motion.div
            className={styles.loadingBar}
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{
              duration: 1.5,
              ease: "easeInOut",
              repeat: Infinity,
            }}
          />
          <div className={styles.loadingBars}>
            {[...Array(10)].map((_, index) => (
              <motion.div
                key={index}
                className={styles.bar}
                initial={{ height: 0 }}
                animate={{ height: `${Math.random() * 100}%` }}
                transition={{
                  duration: 0.8,
                  delay: index * 0.1,
                  repeat: Infinity,
                  repeatType: "reverse",
                }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.chartContainer}>
      <div className={styles.chartHeader}>
        <div className={styles.chartInfo}>
          <div className={styles.chartLegend}>
            <span className={styles.legendDot} style={{ background: chartConfig.color }} />
            <span className={styles.legendText}>
              {data.filter(d => d.hasData !== false).length} {type === "requests" ? "requests" : "days with usage"}
            </span>
            <span className={styles.legendValue}>
              {chartConfig.formatter(
                data.reduce((sum, item) => sum + (item[chartConfig.dataKey] || 0), 0)
              )}
            </span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={data}
          margin={{ top: 15, right: 15, left: 5, bottom: 5 }}
          barCategoryGap={data.length > 30 ? "10%" : data.length > 14 ? "15%" : data.length > 7 ? "20%" : "25%"}
        >
          <defs>
            <pattern id="dotPattern" patternUnits="userSpaceOnUse" width="4" height="1">
              <circle cx="1" cy="0.5" r="0.5" fill="var(--border-color)" opacity="0.5" />
            </pattern>
          </defs>
          <CartesianGrid
            strokeDasharray="0"
            stroke="transparent"
            vertical={false}
            horizontal={false}
          />
          {/* Top reference line with label */}
          <ReferenceLine
            y={maxValue}
            stroke="#7c3aed"
            strokeDasharray="2 2"
            strokeWidth={1}
            opacity={0.5}
            label={{
              value: chartConfig.formatter(maxValue),
              position: "left",
              fill: "#7c3aed",
              fontSize: 11,
              opacity: 0.8
            }}
          />
          {/* Baseline - removed as we'll use custom lines */}
          <XAxis
            dataKey="displayDate"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            height={35}
            interval={data.length > 30 ? Math.floor(data.length / 10) : data.length > 14 ? 3 : data.length > 7 ? 1 : 0}
            tickMargin={10}
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={45}
            tickFormatter={(value: number) => {
              if (type === "spend") return `$${value}`;
              if (value >= 1000) return `${(value / 1000).toFixed(0)}k`;
              return value.toString();
            }}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: "rgba(124, 58, 237, 0.05)", radius: [3, 3, 0, 0] }}
            wrapperStyle={{ outline: "none" }}
            isAnimationActive={false}
          />
          <Bar
            dataKey={chartConfig.dataKey}
            shape={CustomBar}
            animationDuration={1000}
            maxBarSize={data.length > 30 ? 20 : data.length > 7 ? 30 : 40}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={
                  entry.hasData === false
                    ? "transparent"
                    : entry[chartConfig.dataKey] > maxValue * 0.8
                    ? chartConfig.color
                    : `${chartConfig.color}99`
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default UsageChart;
