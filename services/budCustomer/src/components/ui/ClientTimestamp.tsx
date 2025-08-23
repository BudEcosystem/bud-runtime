import React, { useEffect, useState } from 'react';

interface ClientTimestampProps {
  timestamp: string | Date | number;
  format?: 'short' | 'long';
}

export const ClientTimestamp: React.FC<ClientTimestampProps> = ({ timestamp, format = 'short' }) => {
  const [formattedDate, setFormattedDate] = useState<string>('');

  useEffect(() => {
    if (!timestamp) {
      setFormattedDate('');
      return;
    }

    try {
      let dateStr = timestamp;

      // If it's a string without timezone indicator, assume it's UTC and add 'Z'
      if (typeof timestamp === 'string') {
        const hasTimezone = timestamp.endsWith('Z') ||
                           timestamp.match(/[+-]\d{2}:\d{2}$/) ||
                           timestamp.match(/[+-]\d{4}$/);

        if (!hasTimezone) {
          dateStr = timestamp + 'Z';
        }
      }

      const date = new Date(dateStr);

      if (isNaN(date.getTime())) {
        setFormattedDate('Invalid date');
        return;
      }

      if (format === 'long') {
        // With timezone
        const options: Intl.DateTimeFormatOptions = {
          month: 'short',
          day: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
          timeZoneName: 'short'
        };
        setFormattedDate(new Intl.DateTimeFormat('en-US', options).format(date));
      } else {
        // Short format
        const options: Intl.DateTimeFormatOptions = {
          month: 'short',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        };
        setFormattedDate(new Intl.DateTimeFormat('en-US', options).format(date));
      }
    } catch (error) {
      console.error('Error formatting timestamp:', timestamp, error);
      setFormattedDate('Error');
    }
  }, [timestamp, format]);

  // Show loading state during SSR
  if (!formattedDate && timestamp) {
    return <span className="text-gray-400">Loading...</span>;
  }

  return <span>{formattedDate}</span>;
};
