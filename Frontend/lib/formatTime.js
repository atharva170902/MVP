/**
 * Format an ISO timestamp as a short relative string, e.g. "just now",
 * "5 min ago", "3 hours ago", "2 days ago". Falls back to a locale date string
 * for anything older than a week.
 *
 * @param {string} iso - ISO 8601 timestamp
 * @returns {string}
 */
export function timeAgo(iso) {
  if (!iso) return '';

  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';

  const diffMs = Date.now() - then;
  if (diffMs < 0) return 'just now';

  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;

  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`;

  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days} day${days > 1 ? 's' : ''} ago`;

  // Older than a week: show an actual date.
  return new Date(iso).toLocaleDateString();
}
