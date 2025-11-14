import { format } from "date-fns";

// Utility function to add suffix (st, nd, rd, th) to day
const getDayWithSuffix = (day: number): string => {
  if (day > 3 && day < 21) return `${day}th`; // 4th to 20th always end in "th"
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
};

// Main function to format the date string
export const formatDate = (dateString: string | Date | number): string => {
  if (!dateString) return ""; // Return empty string if dateString is empty
  if (typeof dateString === "string" && !dateString.trim()) return ""; // Return empty string if dateString is empty string
  if (typeof dateString === "string" && isNaN(Date.parse(dateString)))
    return ""; // Return empty string if dateString is not a valid date string
  if (dateString instanceof Date && isNaN(dateString.getTime())) return ""; // Return empty string if dateString is not a valid date object

  const date = new Date(dateString); // Convert the string to a Date object

  // return format(date, 'Do MMMM yyyy'); // Return formatted date string
  return format(date, "dd MMM, yyyy"); // Return formatted date string
};

// Format timestamp with time (for tables)
export const formatTimestamp = (dateString: string | Date | number): string => {
  if (!dateString) return "";

  try {
    let dateStr = dateString;

    // If it's a string without timezone indicator, assume it's UTC and add 'Z'
    if (typeof dateString === "string") {
      const hasTimezone =
        dateString.endsWith("Z") ||
        dateString.match(/[+-]\d{2}:\d{2}$/) ||
        dateString.match(/[+-]\d{4}$/);

      if (!hasTimezone) {
        dateStr = dateString + "Z";
      }
    }

    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return "";

    // For client-side use, prefer the ClientTimestamp component
    // This function is kept for non-React contexts
    return format(date, "MMM dd, HH:mm:ss");
  } catch (error) {
    console.error("Error formatting timestamp:", dateString, error);
    return "";
  }
};

// Format timestamp with full date and time (with timezone)
export const formatTimestampWithTZ = (
  dateString: string | Date | number,
): string => {
  if (!dateString) return "";

  try {
    let dateStr = dateString;

    // If it's a string without timezone indicator, assume it's UTC and add 'Z'
    if (typeof dateString === "string") {
      const hasTimezone =
        dateString.endsWith("Z") ||
        dateString.match(/[+-]\d{2}:\d{2}$/) ||
        dateString.match(/[+-]\d{4}$/);

      if (!hasTimezone) {
        dateStr = dateString + "Z";
      }
    }

    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return "";

    // Get timezone abbreviation
    const timeZoneAbbr =
      new Intl.DateTimeFormat("en-US", {
        timeZoneName: "short",
      })
        .formatToParts(date)
        .find((part) => part.type === "timeZoneName")?.value || "";

    // date-fns format() automatically converts to local timezone
    return `${format(date, "MMM dd, yyyy HH:mm:ss")} ${timeZoneAbbr}`;
  } catch (error) {
    console.error("Error formatting timestamp with TZ:", dateString, error);
    return "";
  }
};

// Format date as "MMM, yyyy" (e.g., "Jan, 2025")
export const formatMonthYear = (dateString: string | Date | number): string => {
  if (!dateString) return "";
  if (typeof dateString === "string" && !dateString.trim()) return "";
  if (typeof dateString === "string" && isNaN(Date.parse(dateString)))
    return "";
  if (dateString instanceof Date && isNaN(dateString.getTime())) return "";

  try {
    const date = new Date(dateString);
    return format(date, "MMM, yyyy");
  } catch (error) {
    console.error("Error formatting month-year:", dateString, error);
    return "";
  }
};

export const formatDateWithTime = (date: string) => {
  const d = new Date(date);
  const formattedDate = d.toLocaleDateString("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  });

  const formattedTime = d.toLocaleTimeString([], {
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
  });

  return `${formattedDate}, ${formattedTime}`
}