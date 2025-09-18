import React from "react";
import { motion } from "framer-motion";
import { Icon } from "@iconify/react/dist/iconify.js";
import styles from "./MetricCard.module.scss";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  loading?: boolean;
  trend?: number;
  icon?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  loading = false,
  trend,
  icon,
}) => {
  return (
    <div className={styles.metricCard}>
      {loading ? (
        <div className={styles.loadingContainer}>
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
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className={styles.content}
        >
          <div className={styles.header}>
            <span className={styles.title}>{title}</span>
            {icon && <Icon icon={icon} className={styles.icon} />}
          </div>

          <div className={styles.valueContainer}>
            {typeof value === "string" && value.includes("\n") ? (
              <div className={styles.stackedValue}>
                <span className={styles.value}>{value.split("\n")[0]}</span>
                <span className={styles.quotaValue}>
                  {value.split("\n")[1]}
                </span>
              </div>
            ) : (
              <span className={styles.value}>{value}</span>
            )}
            {trend !== undefined && trend !== 0 && (
              <div
                className={`${styles.trend} ${trend > 0 ? styles.positive : styles.negative}`}
              >
                <Icon
                  icon={trend > 0 ? "ph:trend-up" : "ph:trend-down"}
                  className={styles.trendIcon}
                />
                <span>{Math.abs(trend).toFixed(1)}%</span>
              </div>
            )}
          </div>

          {subtitle && <span className={styles.subtitle}>{subtitle}</span>}
        </motion.div>
      )}
    </div>
  );
};

export default MetricCard;
