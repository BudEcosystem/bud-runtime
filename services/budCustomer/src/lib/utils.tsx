import { differenceInDays, differenceInHours, format, formatDistance, isToday, isYesterday } from "date-fns";
import { Tooltip } from "antd";
import { JSX } from "react";

export const modelNameRegex = /^[a-zA-Z0-9_-]+$/;
export const projectNameRegex = /^[a-zA-Z0-9_\- ]+$/;

export function cn(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

export function capitalize(str: string) {
  if (!str) return "";
  return str
    .split("_") // Split by underscores
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1)) // Capitalize each word
    .join(" "); // Join back with spaces
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

  return <Tooltip title={format(notificationDate, "MMM dd, yyyy HH:mm:ss")}>{time}</Tooltip>;
  // +" " + formatDate(notificationDate) + " " + differenceInDays(today, notificationDate);
}
