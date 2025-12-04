export const formatTimeToHMS = (seconds: number, format: string = ''): string => {
  const hours = Math.floor(seconds / 3600); // Get hours
  const minutes = Math.floor((seconds % 3600) / 60); // Get remaining minutes
  const secs = seconds % 60; // Get remaining seconds

  if(format === 'short') {
    if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
    if (minutes > 0) return `${minutes}m ${secs}s`;
    return `${secs}s`;
  }
  
  // Format the result as 6h:8m:9s
  return `${hours}h:${minutes}m:${secs}s`;
};
