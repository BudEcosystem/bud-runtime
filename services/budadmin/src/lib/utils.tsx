import { Tooltip } from "antd";
import { type ClassValue, clsx } from "clsx";
import {
  differenceInDays,
  differenceInHours,
  format,
  formatDistance,
  isToday,
  isYesterday,
} from "date-fns";
import { validateHeaderValue } from "http";
import { useRouter } from "next/router";
import { useEffect } from "react";
import { ClusterFilter, TimeSeriesData } from "src/hooks/useCluster";
import { formatDate } from "src/utils/formatDate";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function isValidUrl(string) {
  try {
    new URL(string);
    return true;
  } catch (err) {
    return false;
  }
}

export const numberOnlyRegex = new RegExp("^[0-9]*$");
export const endpointNameRegex = new RegExp("^[a-zA-Z0-9-]+$");
export const modelNameRegex = new RegExp("^[a-zA-Z0-9-./]+$");
// allow only alphanumeric characters and hyphen and space
export const projectNameRegex = new RegExp("^[a-zA-Z0-9- ]+$");
export const clusterNameRegex = new RegExp("^[a-zA-Z0-9- ]+$");
export const passwordRegex = new RegExp(
  "^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$",
);

export function isValidEndpointName(name: string) {
  return (
    name &&
    name.length > 0 &&
    name.length <= 100 &&
    endpointNameRegex.test(name)
  );
}

export function isValidModelName(name: string) {
  return (
    name && name.length > 0 && name.length <= 100 && modelNameRegex.test(name)
  );
}

export function isValidProjectName(name: string) {
  return (
    name && name.length > 0 && name.length <= 100 && projectNameRegex.test(name)
  );
}

export function isValidClusterName(name: string) {
  return (
    name && name.length > 0 && name.length <= 100 && clusterNameRegex.test(name)
  );
}

export function getSpecValueWidth(specs: any) {
  const maxNameLength = Math.max(...specs.map((spec) => spec?.value?.length));
  return maxNameLength * 12;
}

export function getSpecValueWidthOddEven(specs: any, index: number) {
  // odd index value width
  return index % 2 === 0
    ? getSpecValueWidth(specs?.filter((spec, i) => i % 2 === 0))
    : // even index value width
      getSpecValueWidth(specs?.filter((spec, i) => i % 2 !== 0));
}

export function capitalize(str: string) {
  if (!str) return "";
  return str
    .split("_") // Split by underscores
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1)) // Capitalize each word
    .join(" "); // Join back with spaces
}

export function statusColor(status: string) {
  switch (status?.toLowerCase()) {
    case "success":
    case "safe":
      return "#479D5F";
    case "critical":
    case "failed":
      return "#EC7575";
    case "medium":
    case "low":
    case "pending":
      return "#D1B854";
    case "high":
      return "#FF895E";
    default:
      return "#EEEEEE";
  }
}

export function formdateDateTime(notificationDate: Date) {
  const today = new Date();
  const isWithinToday = isToday(notificationDate);
  const isWithinYesterday = isYesterday(notificationDate);
  const iswithinAWeek = differenceInDays(today, notificationDate) < 7;
  const iswithinAMonth = differenceInDays(today, notificationDate) < 30;

  const time = isWithinToday
    ? format(notificationDate, "HH:mm")
    : isWithinYesterday
      ? "Yesterday"
      : iswithinAWeek
        ? format(notificationDate, "EEE HH:mm")
        : iswithinAMonth
          ? format(notificationDate, "MMM dd")
          : format(notificationDate, "MMM dd, yyyy");

  return (
    <Tooltip title={format(notificationDate, "MMM dd, yyyy HH:mm:ss")}>
      {time}
    </Tooltip>
  );
  // +" " + formatDate(notificationDate) + " " + differenceInDays(today, notificationDate);
}

export function formatDistanceCustom(date: string | Date) {
  console.log(date);
  if (!date) return "";
  if (date === "Invalid Date") return "";

  return formatDistance(new Date(date), new Date(), {
    addSuffix: true,
    locale: {
      formatDistance: (token, count, options) => {
        if (token === "lessThanXMinutes") {
          return "30 Seconds ago";
        }
        if (token === "aboutXHours") {
          return `${count} hours ago`;
        }
        if (token === "xDays") {
          return `${count} days ago`;
        }
        if (token === "xWeeks") {
          return `${count} weeks ago`;
        }
        if (token === "aboutXMonths") {
          return `${count} months ago`;
        }
        return `${count} ${token}`;
      },
    },
  });
}

// input in from to format to B, KB, MB, GB
export function formatStorageSize(
  size: number,
  from: "B" | "KB" | "MB" | "GB" | "TB" | "Mbps" | "Gbps" | "PB",
) {
  if (size === 0) return "0 B";
  if (size < 1024) {
    return `${size.toFixed(0)} ${from}`;
  } else if (size > 1024) {
    if (from === "B") {
      size = size / 1024;
      from = "KB";
    } else if (from === "KB") {
      size = size / 1024;
      from = "MB";
    } else if (from === "MB") {
      size = size / 1024;
      from = "GB";
    } else if (from === "GB") {
      size = size / 1024;
      from = "TB";
    } else if (from === "TB") {
      size = size / 1024;
      from = "PB";
    } else if (from === "Mbps") {
      size = size / 1024;
      from = "Gbps";
    }
    return `${size.toFixed(2)} ${from}`;
  }
}

export const mapTime = (time: number, selectedSegment: ClusterFilter) => {
  if (selectedSegment === "today") {
    return format(new Date(time * 1000), "HH:mm");
  }
  if (selectedSegment === "7days") {
    return format(new Date(time * 1000), "dd/MM");
  }
  if (selectedSegment === "month") {
    return format(new Date(time * 1000), "dd/MM");
  }
};

export function getCategories(
  selectedSegment: ClusterFilter,
  timeSeries: TimeSeriesData[],
) {
  return timeSeries?.map((item) => mapTime(item.timestamp, selectedSegment));
}

export function getChartData(
  selectedSegment: ClusterFilter,
  timeSeries: TimeSeriesData[],
) {
  return timeSeries?.map((item) => item.value);
}

export function getCommaSeparated(num: number) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function getFormattedToBillions(num: number) {
  if (num >= 1000000000) {
    return `${(num / 1000000000).toFixed(2)}B`;
  }
  return getCommaSeparated(num);
}

export function getInGB(num: number) {
  return `${(num / 1000000000).toFixed(2)} GB`;
}

export function secondsToMilliseconds(seconds) {
  if (seconds >= 1) {
    return Number(seconds.toFixed(2));
  }
  return Number((seconds * 1000).toFixed(2));
}

export function millisecondsToSeconds(milliseconds: number) {
  if (milliseconds >= 1000) {
    return Number((milliseconds / 1000).toFixed(2));
  }
  return Number(milliseconds?.toFixed(2));
}
export function milliToSecUinit(val: number) {
  if (val >= 1000) {
    return `s`;
  }
  return `ms`;
}
export function removeUnderScoreAndCapatalise(value: string) {
  if (value?.includes("_")) {
    return value
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");
  } else {
    return value?.charAt(0).toUpperCase() + value?.slice(1).toLowerCase();
  }
}
