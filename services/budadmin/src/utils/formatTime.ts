export const formatTimeToHMS = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600); // Get hours
  const minutes = Math.floor((seconds % 3600) / 60); // Get remaining minutes
  const secs = seconds % 60; // Get remaining seconds

  // Format the result as 6h:8m:9s
  return `${hours}h:${minutes}m:${secs}s`;
}
