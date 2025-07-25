import { format } from "date-fns";

// Utility function to add suffix (st, nd, rd, th) to day
const getDayWithSuffix = (day: number): string => {
  if (day > 3 && day < 21) return `${day}th`; // 4th to 20th always end in "th"
  switch (day % 10) {
    case 1: return `${day}st`;
    case 2: return `${day}nd`;
    case 3: return `${day}rd`;
    default: return `${day}th`;
  }
};

// Main function to format the date string
export const formatDate = (dateString: string | Date | number): string => {
  if(!dateString) return ''; // Return empty string if dateString is empty
  if(typeof dateString === 'string' && !dateString.trim()) return ''; // Return empty string if dateString is empty string
  if(typeof dateString === 'string' && isNaN(Date.parse(dateString))) return ''; // Return empty string if dateString is not a valid date string
  if(dateString instanceof Date && isNaN(dateString.getTime())) return ''; // Return empty string if dateString is not a valid date object

  const date = new Date(dateString); // Convert the string to a Date object

  // return format(date, 'Do MMMM yyyy'); // Return formatted date string
  return format(date, 'dd MMM, yyyy'); // Return formatted date string
};