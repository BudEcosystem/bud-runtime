export const formatTimeToHMS = (seconds: number, format: 'short' | 'default' = 'default'): string => {
  if (seconds < 0) seconds = 0;
  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (format === 'short') {
    const parts = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || (hours === 0 && minutes === 0)) {
      parts.push(`${secs}s`);
    }
    return parts.length > 0 ? parts.join(' ') : '0s';
  }
  // Format the result as 6h:8m:9s
  return `${hours}h:${minutes}m:${secs}s`;
};