export function timeAgo(value: string): string {
  // The API sends UTC timestamps like "2026-10-25 12:00:00".
  const date = new Date(value.replace(" ", "T") + "Z");
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));

  if (seconds < 60) return "just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} d ago`;

  return date.toLocaleDateString();
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || "?";
}

export function formatSeconds(value: number): string {
  if (value < 1) return "<1 s";
  if (value < 60) return `${Math.round(value)} s`;

  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes} min ${seconds} s`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}