export function formatTimeAgo(timestamp) {
    const seconds = Math.floor((Date.now() - timestamp * 1000) / 1000);
    
    // Define time intervals in seconds
    const intervals = {
      year: 31536000,
      month: 2592000,
      week: 604800,
      day: 86400,
      hour: 3600,
      minute: 60
    };
  
    // Handle special cases
    if (seconds < 5) return 'just now';
    if (seconds < 0) return 'in the future';
  
    // Find the appropriate interval
    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
      const interval = Math.floor(seconds / secondsInUnit);
      
      if (interval >= 1) {
        // Handle singular vs plural
        const suffix = interval === 1 ? '' : 's';
        return `${interval} ${unit}${suffix} ago`;
      }
    }
  
    return 'just now';
  }
  
  // Optional: Add a store that updates timestamps periodically
  import { readable } from 'svelte/store';
  
  export const timeUpdater = readable(Date.now(), set => {
    // Update every minute
    const interval = setInterval(() => {
      set(Date.now());
    }, 60000);
  
    return () => clearInterval(interval);
  });
  
  // Helper function to format a timestamp with the store
  export function createTimestampFormatter(timestamp) {
    let formattedTime = formatTimeAgo(timestamp);
    
    // Subscribe to time updates
    timeUpdater.subscribe(() => {
      formattedTime = formatTimeAgo(timestamp);
    });
  
    return formattedTime;
  }